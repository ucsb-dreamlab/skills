# Fixing Shiny accessibility violations

Fix the app source, not the DOM. Examples are Shiny for Python; R Shiny exposes
the same DOM signals, so the runner works there too, with the equivalent R APIs.

| Violation | Fix |
|---|---|
| `image-alt` on a plot | `@render.plot` emits a bare `<img>` — add alt text: `@render.plot(alt="Line chart of ...")`. Decorative images get `alt=""`. |
| `button-name` | Icon-only `ui.input_action_button` has no accessible name — add `**{"aria-label": "Refresh data"}`, or visible text. |
| `document-title` | Pass `title="..."` to `ui.page_fluid` / `ui.page_sidebar`. |
| `html-has-lang` | Pass `lang="en"` to the same page function. |
| `color-contrast` | Theme colors — adjust the bslib theme or custom CSS to reach 4.5:1 (3:1 for large text). |
| `frame-title` | Embedded plotly/leaflet iframes need a `title` attribute. |
| `label` | Hand-built inputs; prefer `ui.input_*`, which wires labels correctly. |
| `scrollable-region-focusable` | Scrollable table wrappers need `tabindex="0"` to be keyboard reachable. |

The first four are py-shiny defaults — a stock app fails all of them before you
write any custom UI.

## When the run won't settle

The runner exits 2 rather than reporting a pass it can't stand behind. Causes,
in the order worth checking:

- **Timed out waiting for idle.** A slow output keeps `.recalculating` alive.
  Raise `--timeout`; for `--static` shinylive the default is already 120s because
  Pyodide has to boot.
- **"app never rendered".** The DOM had under 10 elements. Usually the app errored
  on startup — run it by hand and look at the console. With `--cmd`, the runner
  prints the app's own output when the port never opens.
- **A widget the gate doesn't know about.** Pass `--ready-selector` with a
  selector that exists only once that widget is up.
- **"window.Shiny never appeared".** Wrong URL, or the page isn't a Shiny app.
  For shinylive the app may live in a same-origin iframe — the runner searches
  frames, but a cross-origin embed is out of reach.

Raising `--stable-ms` helps when outputs render in visible stages and the run
audits between them.

## What axe cannot check

Always relay these to the user; for a dashboard driven by map or chart selection
they are likely the most serious barriers present.

- **Keyboard (WCAG 2.1.1)** — is every control reachable and operable without a
  mouse? Selecting items on a map or plot is the usual failure.
- **Focus (WCAG 2.4.3)** — opening a modal or panel should move focus into it and
  restore it on close.
- **Reactive updates (WCAG 4.1.3)** — when an output changes, is that announced?
  Values that change silently need an `aria-live` region.
