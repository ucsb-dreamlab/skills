---
name: web-a11y
description: Run axe-core accessibility checks (WCAG 2.1 A/AA) against a Quarto site or a Shiny app — live server, shinylive/WASM export, or a shinylive app embedded in a Quarto page — and fix the violations. Use when asked to audit, test, or fix accessibility/a11y/WCAG issues in a Quarto website, book, or docs site, or in a Shiny app or dashboard.
---

# Quarto and Shiny accessibility checks

Runs axe-core in headless Chrome, scoped to WCAG 2.1 level A and AA. Serious and
critical violations fail the run; moderate and minor are reported as warnings.

## Setup (once per install)

The runners need their dependencies installed **inside this skill's own
directory** — the one containing this SKILL.md. Don't guess that path: when
installed as a plugin it is version-hashed and changes on every update. Use the
real path of this file, which you already know when this skill loads:

```bash
SKILL_DIR=<directory containing this SKILL.md>
npm install --prefix "$SKILL_DIR"
```

Skip it if `$SKILL_DIR/node_modules` already exists. Re-run it after a plugin
update, which lands in a fresh directory.

Requires Node 18+ and a system Chrome or Chromium. The runner checks
`$CHROME_PATH`, `/usr/bin/google-chrome`, `/usr/bin/chromium`,
`/usr/bin/chromium-browser`, and the macOS Chrome bundle.

## Which runner

Run these from the project being audited, with `$SKILL_DIR` as above.

| Target | Command |
|---|---|
| Rendered Quarto site | `node "$SKILL_DIR/scripts/quarto.mjs"` |
| Shiny app you want launched | `node "$SKILL_DIR/scripts/shiny.mjs" --cmd "shiny run --port 8080 app.py"` |
| Shiny app already running | `node "$SKILL_DIR/scripts/shiny.mjs" --url http://127.0.0.1:8080` |
| shinylive / WASM export | `node "$SKILL_DIR/scripts/shiny.mjs" --static ./site` |

A Quarto page that *embeds* a shinylive app still uses `quarto.mjs` — it detects
the app, waits for it to render, and audits inside its frame.

Both write one JSON report per target to `--out` (default `a11y-report/`) and
exit `0` clean, `1` serious/critical, `2` setup error. Add the report directory
to `.gitignore`. Read a report for the failing node's `html` and `target`
selector when the console summary isn't enough.

## Quarto

```bash
quarto render
node "$SKILL_DIR/scripts/quarto.mjs"
```

Output directory is auto-detected (`_site`, `_book`, then `docs`); every `.html`
file found there is checked. Options: `--site DIR` if auto-detection picks wrong,
`--out DIR`, and trailing paths to check only those pages.

Fix the **source** (`.qmd`, `_quarto.yml`, `custom.scss`), never the rendered
HTML — rendering overwrites it. For the violation-to-fix table and the
collapsible-callout patch, read `references/quarto.md`.

## Shiny

A Shiny app is not a set of static pages: its DOM is populated asynchronously and
its meaningful UI states exist only after interaction. So `shiny.mjs` audits
**states**, and gates every audit on the app having actually rendered.

Without `--states`, only the landing state is audited — usually a small fraction
of the app. Describe the states worth checking in a JSON file (see
`states.example.json`):

```json
{
  "states": [
    { "name": "default", "steps": [] },
    { "name": "station-b", "steps": [
      { "select": "#station", "value": "b" },
      { "wait": "#summary_text" }
    ]}
  ]
}
```

Steps: `click`, `select` + `value`, `fill` + `value`, `wait` (selector), `waitMs`.
Each state gets a fresh page load and its own report; the run ends with a roll-up
that dedups findings by rule + element, so one themewide problem reads as one
finding.

Options: `--states FILE`, `--timeout SECONDS` (default 30, or 120 for `--static`),
`--ready-selector CSS`, `--stable-ms MS` (default 600).

For the violation-to-fix table and readiness troubleshooting, read
`references/shiny.md`.

### How readiness is decided

Auditing too early silently reports a clean pass on an empty page — the worst
failure mode here. Before each audit the runner requires, held stable for
`--stable-ms`: `window.Shiny` present, no `shiny-busy` class on `<html>`, and zero
`.recalculating` elements. It then asserts the DOM is non-trivial and exits 2
rather than passing if it is not.

`shiny-busy` alone is **not** sufficient — it clears before outputs finish
rendering.

## Reporting results

Summarize per page or per state: counts by impact, then the specific violations
with the source construct responsible. Propose source-level fixes; never edit
files in a rendered output directory.

Whenever a Shiny app was involved, always relay the manual-check footer the run
prints. axe cannot see keyboard reachability of map/plot selection (WCAG 2.1.1),
focus handling on modal open (2.4.3), or whether reactive updates are announced
(4.1.3). For a dashboard where selection happens on a map or chart, those are
likely the most serious barriers present, and no axe run will surface them.
