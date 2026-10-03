import { createRequire } from 'node:module';
import { dirname, resolve, join } from 'node:path';
import { mkdir, readdir, copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const target = fileURLToPath(new URL('../../static/ocr/', import.meta.url));
const engine = dirname(require.resolve('tesseract.js/package.json'));
const core = dirname(createRequire(join(engine, 'package.json')).resolve('tesseract.js-core/package.json'));
const language = dirname(require.resolve('@tesseract.js-data/eng/package.json'));
await mkdir(target, { recursive: true });
await copyFile(join(engine, 'dist/worker.min.js'), join(target, 'worker.min.js'));
await copyFile(join(engine, 'LICENSE.md'), join(target, 'tesseract-js-LICENSE.txt'));
await copyFile(join(core, 'LICENSE'), join(target, 'tesseract-core-LICENSE.txt'));
await copyFile(join(language, 'package.json'), join(target, 'english-data-package.json'));
for (const name of await readdir(core)) {
  if (/^tesseract-core.*\.wasm(\.js)?$/.test(name)) await copyFile(join(core, name), join(target, name));
}
await copyFile(resolve(language, '4.0.0_best_int/eng.traineddata.gz'), join(target, 'eng.traineddata.gz'));
console.log('Prepared self-hosted OCR worker, cores, and English recognition data.');
