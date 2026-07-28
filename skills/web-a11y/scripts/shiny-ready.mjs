// Readiness gating for Shiny apps, wherever they turn up.
//
// Used by shiny.mjs for a whole app, and by quarto.mjs for a shinylive app
// embedded in an otherwise static page. Auditing before the app has rendered
// silently reports a clean pass on a loading shell, which is the worst failure
// mode available here — so everything in this file exists to prevent it.

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Shinylive may render the app inside a same-origin iframe; axe has to run in
// whichever frame actually owns the app. Returns null if there is no Shiny here.
export async function findShinyFrame(page, timeout) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    for (const frame of page.frames()) {
      try {
        if (await frame.evaluate(() => typeof window.Shiny !== 'undefined')) return frame;
      } catch {
        // frame navigated out from under us
      }
    }
    await sleep(250);
  }
  return null;
}

// Cheap one-shot probe: is there a Shiny app on this page at all? Used to decide
// whether a page needs the idle gate, without paying findShinyFrame's full timeout.
export async function hasShiny(page) {
  for (const frame of page.frames()) {
    try {
      const found = await frame.evaluate(
        () => typeof window.Shiny !== 'undefined'
          || document.querySelector('.shinylive-app, shinylive-app, [class*="shinylive"]') !== null,
      );
      if (found) return true;
    } catch {
      // frame went away
    }
  }
  return false;
}

// The load-bearing gate. `shiny-busy` on <html> clears before outputs finish
// rendering, so the per-output `.recalculating` class and a stability window are
// what actually tell us the DOM has settled.
export async function waitForShinyIdle(frame, { timeout, stableMs, readySelector }) {
  const deadline = Date.now() + timeout;
  let stableSince = null;
  while (Date.now() < deadline) {
    let idle = false;
    try {
      idle = await frame.evaluate((sel) => {
        if (typeof window.Shiny === 'undefined') return false;
        if (document.documentElement.classList.contains('shiny-busy')) return false;
        if (document.querySelectorAll('.recalculating').length > 0) return false;
        if (sel && !document.querySelector(sel)) return false;
        return true;
      }, readySelector);
    } catch {
      idle = false;
    }
    if (idle) {
      stableSince ??= Date.now();
      if (Date.now() - stableSince >= stableMs) return true;
    } else {
      stableSince = null;
    }
    await sleep(150);
  }
  return false;
}

// Never report a clean pass on a loading shell.
export async function assertRendered(frame) {
  const shape = await frame.evaluate(() => ({
    elements: document.querySelectorAll('body *').length,
    text: document.body.innerText.trim().length,
  }));
  if (shape.elements < 10) {
    throw new Error(
      `app never rendered (only ${shape.elements} elements, ${shape.text} chars of text). `
      + 'Raise --timeout, or pass --ready-selector for a selector that exists once the app is up.',
    );
  }
}

export function printManualChecks() {
  console.log(`
=== Not covered by axe — check these by hand ===
  - Keyboard: is every control reachable and operable without a mouse? Selecting
    items on a map or plot is the usual failure (WCAG 2.1.1).
  - Focus: opening a modal or panel should move focus into it and restore it on
    close (WCAG 2.4.3).
  - Reactive updates: when an output changes, is that announced? Values that
    change silently need an aria-live region (WCAG 4.1.3).`);
}
