// axe-core accessibility checks (WCAG 2.1 A + AA) for a Shiny app.
//
// Usage:
//   node shiny.mjs --url http://127.0.0.1:8080
//   node shiny.mjs --cmd "shiny run --port 8080 app.py"
//   node shiny.mjs --static ./site          # shinylive export
//
// Unlike a static site, a Shiny app has no directory of pages: its meaningful UI
// states exist only after interaction, and its DOM is populated asynchronously.
// So this audits *states* (see --states), and gates every audit on the app
// actually having rendered.

import { spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import {
  launchBrowser, serveStatic, auditPage, countImpacts,
  writeReport, printViolations, printSummary, reportPath, IMPACTS,
} from './axe-run.mjs';
import {
  sleep, findShinyFrame, waitForShinyIdle, assertRendered, printManualChecks,
} from './shiny-ready.mjs';

function parseArgs(argv) {
  const opts = {
    url: null, cmd: null, static: null, states: null, out: 'a11y-report',
    readySelector: null, timeout: null, stableMs: 600,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--url') opts.url = argv[++i];
    else if (arg === '--cmd') opts.cmd = argv[++i];
    else if (arg === '--static') opts.static = argv[++i];
    else if (arg === '--states') opts.states = argv[++i];
    else if (arg === '--out') opts.out = argv[++i];
    else if (arg === '--ready-selector') opts.readySelector = argv[++i];
    else if (arg === '--timeout') opts.timeout = Number(argv[++i]) * 1000;
    else if (arg === '--stable-ms') opts.stableMs = Number(argv[++i]);
    else throw new Error(`Unknown argument: ${arg}`);
  }
  // Pyodide has to boot before a shinylive build renders anything.
  if (opts.timeout === null) opts.timeout = opts.static ? 120000 : 30000;
  return opts;
}

async function waitForPort(url, timeout) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(2000) });
      if (res.ok) return true;
    } catch {
      // not up yet
    }
    await sleep(300);
  }
  return false;
}

// Start the app ourselves and make sure it dies with us.
//
// `detached` puts the shell and the server it spawns in one process group, so we
// can signal the whole group. Killing only the shell would orphan the server, and
// its still-open stdio pipes would keep this process alive forever.
function startApp(cmd) {
  const child = spawn(cmd, { shell: true, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const log = [];
  child.stdout.on('data', (d) => log.push(d.toString()));
  child.stderr.on('data', (d) => log.push(d.toString()));
  const kill = () => {
    try {
      process.kill(-child.pid, 'SIGTERM');
    } catch {
      // already gone
    }
  };
  process.on('exit', kill);
  process.on('SIGINT', () => { kill(); process.exit(130); });
  return { child, log, kill };
}

async function applyStep(frame, step) {
  if (step.click) await frame.click(step.click);
  else if (step.select) await frame.select(step.select, String(step.value));
  else if (step.fill) await frame.type(step.fill, String(step.value));
  else if (step.wait) await frame.waitForSelector(step.wait, { timeout: 15000 });
  else if (step.waitMs) await sleep(step.waitMs);
  else throw new Error(`Unrecognized step: ${JSON.stringify(step)}`);
}

async function loadStates(file) {
  if (!file) return { states: [{ name: 'default', steps: [] }] };
  return JSON.parse(await readFile(path.resolve(file), 'utf8'));
}

function printRollup(findings) {
  if (findings.size === 0) return;
  console.log('\n=== Unique violations across states ===');
  const sorted = [...findings.values()].sort(
    (a, b) => IMPACTS.indexOf(a.impact) - IMPACTS.indexOf(b.impact),
  );
  for (const f of sorted) {
    console.log(`  (${f.impact}) ${f.id} — ${f.target}`);
    console.log(`      states: ${[...f.states].join(', ')}`);
  }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (!opts.url && !opts.cmd && !opts.static) {
    console.error('Pass one of --url URL, --cmd "shiny run ...", or --static DIR.');
    process.exit(2);
  }

  const config = await loadStates(opts.states);
  let baseUrl = opts.url || config.url;
  let server = null;
  let app = null;

  if (opts.static) {
    ({ server } = await serveStatic(opts.static).then((s) => {
      baseUrl = `http://127.0.0.1:${s.port}`;
      return s;
    }));
  } else if (opts.cmd) {
    app = startApp(opts.cmd);
    // `shiny run --port 8080` tells us where to look; 8000 is shiny's default.
    baseUrl ||= `http://127.0.0.1:${opts.cmd.match(/--port[= ](\d+)/)?.[1] ?? 8000}`;
    if (!(await waitForPort(baseUrl, 60000))) {
      console.error(`App at ${baseUrl} never came up. Output:\n${app.log.join('')}`);
      app.kill();
      process.exit(2);
    }
  }

  const browser = await launchBrowser();
  const rows = [];
  const findings = new Map();

  try {
    for (const state of config.states) {
      const page = await browser.newPage();
      try {
        await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: opts.timeout });
        const frame = await findShinyFrame(page, opts.timeout);
        if (!frame) throw new Error('window.Shiny never appeared — is this a Shiny app?');

        await waitForShinyIdle(frame, opts);
        for (const step of state.steps || []) {
          await applyStep(frame, step);
          await waitForShinyIdle(frame, { ...opts, timeout: 15000 });
        }
        if (!(await waitForShinyIdle(frame, opts))) {
          throw new Error(`app still busy after ${opts.timeout / 1000}s`);
        }
        await assertRendered(frame);

        const result = await auditPage(frame);
        await writeReport(opts.out, state.name, result);
        printViolations(state.name, result.violations);
        rows.push({ label: state.name, counts: countImpacts(result.violations) });

        for (const v of result.violations) {
          for (const node of v.nodes) {
            const target = node.target.join(' ');
            const key = `${v.id}|${target}`;
            const found = findings.get(key)
              ?? { id: v.id, impact: v.impact, target, states: new Set() };
            found.states.add(state.name);
            findings.set(key, found);
          }
        }
      } catch (err) {
        console.error(`  ! ${state.name}: ${err.message}`);
        rows.push({ label: state.name, error: err.message });
      } finally {
        await page.close();
      }
    }
  } finally {
    await browser.close();
    if (server) server.close();
    if (app) app.kill();
  }

  const failed = printSummary(rows);
  printRollup(findings);
  console.log(`\nReports written to ${reportPath(opts.out)}/`);
  printManualChecks();

  if (failed) {
    console.error('\nFAIL: serious or critical accessibility violations found.');
    process.exit(1);
  }
  console.log('\nPASS: no serious or critical violations.');
  // Exit explicitly: a stray handle from the app we spawned must not hang the run.
  process.exit(0);
}

main().catch((err) => {
  console.error(err);
  process.exit(2);
});
