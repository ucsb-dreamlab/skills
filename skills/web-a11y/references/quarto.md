# Fixing Quarto accessibility violations

Fix the **source** (`.qmd`, `_quarto.yml`, `custom.scss`), not the rendered HTML —
the next `quarto render` overwrites it.

| Violation | Fix |
|---|---|
| `image-alt` | Add alt text: `![Description](img.png)`. Decorative images get `![](img.png){fig-alt=""}`. |
| `color-contrast` | Adjust theme colors in `custom.scss` / the `theme:` setting to reach 4.5:1 (3:1 for large text). |
| `heading-order` | Fix heading levels in the `.qmd`; don't jump `##` → `####`. |
| `link-name` | Give icon-only or duplicated links real text, or `aria-label`. |
| `html-has-lang` | Set `lang: en` in `_quarto.yml`. |
| `region` / `landmark-*` | Usually theme-level; check custom includes and partials. |
| `aria-allowed-attr` on callouts | Quarto bug — use the post-render fix below. |

## Collapsible callout fix

Quarto renders `collapse="true"` callout headers as a `<div>` with
`aria-expanded` but no role that permits it, a critical `aria-allowed-attr`
violation. Patch it after render by adding to `_quarto.yml`:

```yaml
project:
  post-render:
    - node ~/.agents/skills/web-a11y/scripts/fix-callout-a11y.mjs
```

The script patches `QUARTO_PROJECT_OUTPUT_FILES` when Quarto sets it, and
otherwise walks the output directory (`_site`, `_book`, or `docs`, or a directory
passed as its first argument).

Copy the script into the project's own `scripts/` directory instead if the
project is shared and collaborators won't have the skill installed.

## Embedded shinylive apps

A Quarto page hosting a shinylive app is audited by `quarto.mjs` like any other
page, except the runner waits for the app to render and then runs axe inside the
app's frame. Such pages are labelled `(shinylive)` in the console output, and the
run prints the manual-check footer.

Violations reported inside an embedded app are app-source problems — see
`references/shiny.md` for the fix table. Pyodide boot is slow, so these pages get
a 120s budget; if one times out, check that the app works in a real browser
before treating it as a tooling problem.
