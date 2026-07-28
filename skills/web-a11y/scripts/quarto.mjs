// axe-core accessibility checks (WCAG 2.1 A + AA) for a rendered Quarto site.
//
// Usage:  node quarto.mjs [--site DIR] [--out DIR] [page.html ...]
//
// Serves the rendered site over a local HTTP server, runs axe-core in headless
// Chrome against each page, writes one JSON report per page, prints a summary,
// and exits 1 if any `serious` or `critical` violation is found.
//
// Pages that embed a shinylive app are gated on the app rendering before they
// are audited — otherwise axe sees a loading shell and reports a false pass.

import { readdir } from 'node:fs/promises';
import path from 'node:path';
import {
  exists, launchBrowser, serveStatic, auditPage, countImpacts,
  writeReport, printViolations, printSummary, reportPath,
} from './axe-run.mjs';
import {
  hasShiny, findShinyFrame, waitForShinyIdle, assertRendered, printManualChecks,
} from './shiny-ready.mjs';

const SKIP_DIRS = new Set(['site_libs', '.quarto']);

// Pyodide has to boot before an embedded shinylive app renders anything.
const SHINY_TIMEOUT = 120000;
const STABLE_MS = 600;

function parseArgs(argv) {
  const opts = { site: null, out: 'a11y-report', pages: [] };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--site') opts.site = argv[++i];
    else if (argv[i] === '--out') opts.out = argv[++i];
    else if (argv[i]) opts.pages.push(argv[i]);
  }
  return opts;
}

async function resolveSiteDir(explicit) {
  if (explicit) return path.resolve(explicit);
  for (const dir of ['_site', '_book', 'docs']) {
    if (await exists(path.join(process.cwd(), dir, 'index.html'))) return path.resolve(dir);
  }
  return null;
}

// Every .html file in the site, relative to siteDir.
async function findPages(siteDir) {
  const pages = [];
  async function walk(dir, prefix) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      if (SKIP_DIRS.has(entry.name)) continue;
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      if (entry.isDirectory()) await walk(path.join(dir, entry.name), rel);
      else if (entry.name.endsWith('.html')) pages.push(rel);
    }
  }
  await walk(siteDir, '');
  return pages.sort();
}

// A static page audits as-is. A page hosting a shinylive app has to settle first
// — but the audit still runs from the top document, so the host page's own
// content is checked alongside the app's. auditPage injects axe into every frame.
async function auditTarget(page) {
  if (!(await hasShiny(page))) return { result: await auditPage(page), shiny: false };

  const frame = await findShinyFrame(page, SHINY_TIMEOUT);
  if (!frame) throw new Error('shinylive app found but window.Shiny never appeared');
  if (!(await waitForShinyIdle(frame, {
    timeout: SHINY_TIMEOUT, stableMs: STABLE_MS, readySelector: null,
  }))) {
    throw new Error(`embedded app still busy after ${SHINY_TIMEOUT / 1000}s`);
  }
  await assertRendered(frame);
  return { result: await auditPage(page), shiny: true };
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const siteDir = await resolveSiteDir(opts.site);
  if (!siteDir || !(await exists(siteDir))) {
    console.error('No rendered site found. Run `quarto render` first, or pass --site DIR.');
    process.exit(2);
  }

  const pages = opts.pages.length > 0 ? opts.pages : await findPages(siteDir);
  const { server, port } = await serveStatic(siteDir);
  const browser = await launchBrowser();
  const rows = [];
  let sawShiny = false;

  try {
    for (const pagePath of pages) {
      const page = await browser.newPage();
      try {
        const url = `http://127.0.0.1:${port}/${pagePath.replace(/^\//, '')}`;
        const response = await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });
        if (!response || !response.ok()) {
          const status = response ? `HTTP ${response.status()}` : 'no response';
          console.error(`  ! ${pagePath}: ${status} (skipped)`);
          rows.push({ label: pagePath, error: status });
          continue;
        }
        const { result, shiny } = await auditTarget(page);
        if (shiny) sawShiny = true;
        await writeReport(opts.out, pagePath, result);
        printViolations(shiny ? `${pagePath} (shinylive)` : pagePath, result.violations);
        rows.push({ label: pagePath, counts: countImpacts(result.violations) });
      } catch (err) {
        console.error(`  ! ${pagePath}: ${err.message}`);
        rows.push({ label: pagePath, error: err.message });
      } finally {
        await page.close();
      }
    }
  } finally {
    await browser.close();
    server.close();
  }

  const failed = printSummary(rows);
  console.log(`\nReports written to ${reportPath(opts.out)}/`);
  if (sawShiny) printManualChecks();

  if (failed) {
    console.error('\nFAIL: serious or critical accessibility violations found.');
    process.exit(1);
  }
  console.log('\nPASS: no serious or critical violations.');
}

main().catch((err) => {
  console.error(err);
  process.exit(2);
});
