import { readdir, mkdir, copyFile } from 'node:fs/promises';
const destination = new URL('../dist/licenses/', import.meta.url);
await mkdir(destination, { recursive: true });
for (const dependency of ['chart.js', 'lucide', 'zod', 'vite']) {
  const directory = new URL(`../node_modules/${dependency}/`, import.meta.url);
  const licenses = (await readdir(directory)).filter(name => /^license(?:\.|$)/i.test(name));
  if (!licenses.length) throw new Error(`Missing dependency license: ${dependency}`);
  for (const file of licenses) await copyFile(new URL(file, directory), new URL(`${dependency.replace('.', '-')}-${file}`, destination));
}