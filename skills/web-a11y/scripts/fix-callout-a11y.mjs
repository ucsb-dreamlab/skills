#!/usr/bin/env node
// Post-render fix for Quarto collapsible callouts.
//
// Quarto emits collapsible callout headers as a <div> carrying
// `data-bs-toggle="collapse"` and `aria-expanded`, but with no role that permits
// `aria-expanded`. axe-core flags this as a critical `aria-allowed-attr`
// violation. Adding `role="button"` makes the ARIA state valid.
//
// Usage:  node fix-callout-a11y.mjs [siteDir]
// As a Quarto `post-render` script it patches QUARTO_PROJECT_OUTPUT_FILES;
// otherwise it walks siteDir (default: _site, _book, or docs).

import { readFile, writeFile, readdir, access } from 'node:fs/promises';
import path from 'node:path';

const HEADER_RE = /<div class="callout-header([^"]*)"((?:(?!role=)[^>])*?data-bs-toggle="collapse"(?:(?!role=)[^>])*?)>/g;
const exists = (p) => access(p).then(() => true, () => false);

async function siteDir() {
  const explicit = process.argv[2];
  if (explicit) return path.resolve(explicit);
  for (const dir of ['_site', '_book', 'docs']) {
    if (await exists(path.join(process.cwd(), dir, 'index.html'))) return path.resolve(dir);
  }
  throw new Error('No rendered site found. Pass the output directory as an argument.');
}

async function htmlFiles() {
  const fromQuarto = process.env.QUARTO_PROJECT_OUTPUT_FILES;
  if (fromQuarto) {
    return fromQuarto.split('\n').map((f) => f.trim())
      .filter((f) => f.endsWith('.html')).map((f) => path.resolve(f));
  }
  const files = [];
  async function walk(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) await walk(full);
      else if (entry.name.endsWith('.html')) files.push(full);
    }
  }
  await walk(await siteDir());
  return files;
}

let patchedFiles = 0;
let patchedHeaders = 0;

for (const file of await htmlFiles()) {
  let html;
  try {
    html = await readFile(file, 'utf8');
  } catch {
    continue;
  }
  let count = 0;
  const next = html.replace(HEADER_RE, (_m, cls, attrs) => {
    count += 1;
    return `<div class="callout-header${cls}"${attrs} role="button">`;
  });
  if (count > 0) {
    await writeFile(file, next);
    patchedFiles += 1;
    patchedHeaders += count;
  }
}

if (patchedHeaders > 0) {
  console.log(`a11y: added role="button" to ${patchedHeaders} callout header(s) in ${patchedFiles} file(s).`);
}
