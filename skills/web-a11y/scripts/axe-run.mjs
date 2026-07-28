// axe-core audit core for the web-a11y skill.
//
// Framework-neutral half of the skill: browser launch, a static file server, axe
// injection scoped to WCAG 2.1 A + AA, JSON reports, and the summary table / exit
// contract. Anything that knows about Quarto or Shiny belongs in the entry points
// (quarto.mjs, shiny.mjs), not here.

import { createServer } from 'node:http';
import { readFile, mkdir, writeFile, access } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import puppeteer from 'puppeteer-core';

const require = createRequire(import.meta.url);

const AXE_SOURCE = require.resolve('axe-core/axe.min.js');
const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
export const IMPACTS = ['critical', 'serious', 'moderate', 'minor'];

const CHROME_CANDIDATES = [
  process.env.CHROME_PATH,
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
];

const TYPES = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.gif': 'image/gif', '.webp': 'image/webp', '.ico': 'image/x-icon',
  '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf',
  '.wasm': 'application/wasm', '.whl': 'application/octet-stream',
  '.data': 'application/octet-stream', '.txt': 'text/plain; charset=utf-8',
};

export const exists = (p) => access(p).then(() => true, () => false);

async function findChrome() {
  for (const candidate of CHROME_CANDIDATES) {
    if (candidate && (await exists(candidate))) return candidate;
  }
  throw new Error('No Chrome/Chromium found. Set CHROME_PATH to the browser executable.');
}

export async function launchBrowser() {
  return puppeteer.launch({
    executablePath: await findChrome(),
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
}

// Static file server for a rendered site directory. Sets cross-origin isolation
// headers, which any WASM payload embedded in the site may need; harmless otherwise.
export function serveStatic(rootDir) {
  const root = path.resolve(rootDir);
  const server = createServer(async (req, res) => {
    const headers = {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    };
    try {
      let urlPath = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      if (urlPath.endsWith('/')) urlPath += 'index.html';
      const filePath = path.join(root, path.normalize(urlPath));
      if (!filePath.startsWith(root)) return void res.writeHead(403, headers).end('Forbidden');
      const body = await readFile(filePath);
      headers['Content-Type'] = TYPES[path.extname(filePath)] || 'application/octet-stream';
      res.writeHead(200, headers).end(body);
    } catch {
      res.writeHead(404, headers).end('Not found');
    }
  });
  return new Promise((resolve, reject) => {
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}

// Inject axe and run it against the current DOM, scoped to WCAG 2.1 A + AA.
//
// Takes a Page or a Frame. Given a Page, axe is injected into every same-origin
// frame first: axe aggregates results across frames, but only for frames it is
// actually present in, so a page embedding an app in an iframe would otherwise
// report the host document alone. Given a Frame, only that frame is audited.
export async function auditPage(target) {
  const frames = typeof target.frames === 'function' ? target.frames() : [target];
  await Promise.all(frames.map(
    (f) => f.addScriptTag({ path: AXE_SOURCE }).catch(() => {}), // cross-origin: skip
  ));
  return target.evaluate(
    (tags) => axe.run(document, { runOnly: { type: 'tag', values: tags } }),
    WCAG_TAGS,
  );
}

export function countImpacts(violations) {
  const counts = { critical: 0, serious: 0, moderate: 0, minor: 0 };
  for (const v of violations) counts[v.impact || 'minor'] += 1;
  return counts;
}

export async function writeReport(reportDir, slug, result) {
  await mkdir(reportDir, { recursive: true });
  const safe = slug.replace(/[\\/]/g, '__').replace(/\.html$/, '');
  await writeFile(path.join(reportDir, `${safe}.json`), JSON.stringify(result, null, 2));
}

// Per-target violation detail. `label` is a page path or a UI state name.
export function printViolations(label, violations) {
  if (violations.length === 0) {
    console.log(`\n${label}\n  No violations.`);
    return;
  }
  console.log(`\n${label}`);
  for (const v of violations) {
    const mark = v.impact === 'serious' || v.impact === 'critical' ? 'FAIL' : 'warn';
    console.log(`  [${mark}] (${v.impact}) ${v.id}: ${v.help} — ${v.nodes.length} node(s)`);
    console.log(`         ${v.helpUrl}`);
  }
}

// rows: [{ label, counts } | { label, error }]. Returns true if anything failed.
export function printSummary(rows, heading = 'Accessibility summary (WCAG 2.1 A + AA)') {
  const width = Math.max(20, ...rows.map((r) => r.label.length));
  console.log(`\n=== ${heading} ===`);
  console.log('target'.padEnd(width) + ' crit  seri  mod  min');
  let failed = false;
  for (const row of rows) {
    if (row.error) {
      console.log(`${row.label.padEnd(width)}  (${row.error})`);
      failed = true;
      continue;
    }
    if (row.counts.serious > 0 || row.counts.critical > 0) failed = true;
    const cells = IMPACTS.map((k, i) => String(row.counts[k]).padStart(i < 2 ? 4 : 3));
    console.log(`${row.label.padEnd(width)} ${cells.join('  ')}`);
  }
  return failed;
}

export function reportPath(reportDir) {
  const rel = path.relative(process.cwd(), path.resolve(reportDir));
  return rel.startsWith('..') ? path.resolve(reportDir) : rel;
}
