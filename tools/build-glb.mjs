#!/usr/bin/env node
/**
 * build-glb.mjs — відтворювана підготовка моделі квартири для вебу.
 *
 *   node tools/build-glb.mjs "новий концепт/Квартира.glb" img/3d/kv-b21.glb
 *
 * Навіщо це скрипт, а не ручні правки в Blender:
 * ArchiCAD→Blender→glTF заново ламає alphaMode при КОЖНОМУ реекспорті. Скрипт
 * ідемпотентний і переживе наступну ревізію від архітектора.
 *
 * Залежності (лише для збірки, не для сайту):
 *   npm i -D @gltf-transform/core @gltf-transform/extensions @gltf-transform/functions sharp
 *
 * ДОКАЗОВА БАЗА (див. thoughts/research/2026-07-15-apartment-glb-walkthrough.md §3):
 *   Усі 15 матеріалів з alphaMode=BLEND виміряні — у ЖОДНОЇ текстури немає жодного
 *   справді невидимого пікселя (near-zero alpha = 0.0%). У трьох випадках альфа-канал
 *   корелює з яскравістю на 0.88–0.97, тобто це bump-мапа, помилково підключена в
 *   канал прозорості. Прозорість не робить нічого, окрім молочної пелени на стінах,
 *   артефактів сортування глибини (depthWrite=false) і подвійного overdraw.
 */
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, weld, textureCompress } from '@gltf-transform/functions';
import sharp from 'sharp';
import { statSync } from 'node:fs';

const [, , inPath = 'новий концепт/Квартира.glb', outPath = 'img/3d/kv-b21.glb'] = process.argv;

/**
 * Матеріали, які МАЮТЬ лишитись прозорими. Наразі — жоден.
 * У цій моделі скло («Стекло - Голубое») експортоване як OPAQUE, а бетон як BLEND —
 * інверсія, доказ що alphaMode тут суто транспортний артефакт, а не авторський намір.
 * Якщо архітектор колись віддасть модель зі справжнім склом — додати сюди.
 */
const KEEP_BLEND = /(^__never_match__$)/i;

const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(inPath);
const root = doc.getRoot();

// ── 1. alphaMode: BLEND → OPAQUE ────────────────────────────────────────────
let fixed = 0;
for (const mat of root.listMaterials()) {
  const name = mat.getName() || '(unnamed)';
  if (mat.getAlphaMode() === 'BLEND' && !KEEP_BLEND.test(name)) {
    mat.setAlphaMode('OPAQUE');
    mat.setAlpha(1.0); // прибрати залишковий baseColorFactor[3] < 1
    fixed++;
  }
}
console.log(`alphaMode BLEND→OPAQUE: ${fixed} матеріалів`);

// ── 2. doubleSided — НЕ чіпаємо ─────────────────────────────────────────────
// 38/38 матеріалів doubleSided. Вимкнення = ~2× менше растеризації, АЛЕ якщо
// у Blender є перевернуті нормалі — ці поверхні стануть НЕВИДИМИМИ (дірки в стінах).
// Без візуального доказу в реальному браузері це зміна наосліп. Перемикається
// в рантаймі через ?side=front для A/B-перевірки — див. tour page.
console.log(`doubleSided: ${root.listMaterials().filter((m) => m.getDoubleSided()).length}/${root.listMaterials().length} — лишено як є (потребує візуального доказу)`);

// ── 3. Геометрія + текстури ────────────────────────────────────────────────
// БЕЗ simplify: 50k tris уже мало, а децимація зріже укоси дверей, віконні рами,
// плінтуси — саме ті чіткі ребра, які роблять архвіз архітектурою.
// БЕЗ palette/join/flatten: знищили б імена нод і мапінг матеріалів.
// БЕЗ Draco/meshopt: геометрія не є проблемою ваги (текстури = 64% файлу);
// виграш ~100 КБ ціною декодера + воркера + blob: у CSP.
const trisBefore = countTris(root);
await doc.transform(
  dedup(),
  prune(),
  weld(),
  // Текстури вже ≤1024 (найбільша 999×443) — resize тут запобіжник, не оптимізація.
  textureCompress({ encoder: sharp, targetFormat: 'webp', quality: 82, resize: [1024, 1024] }),
);
const trisAfter = countTris(root);

await io.write(outPath, doc);

// ── 4. Gates ───────────────────────────────────────────────────────────────
const blendLeft = root.listMaterials().filter((m) => m.getAlphaMode() === 'BLEND').length;
const bytes = statSync(outPath).size;
const srcBytes = statSync(inPath).size;

console.log(`\nтрикутники: ${trisBefore.toLocaleString()} → ${trisAfter.toLocaleString()}`);
console.log(`розмір:     ${(srcBytes / 1048576).toFixed(2)} MB → ${(bytes / 1048576).toFixed(2)} MB (−${(100 - (bytes / srcBytes) * 100).toFixed(0)}%)`);
console.log(`→ ${outPath}`);

let failed = false;
const gate = (ok, msg) => { console.log(`${ok ? '✓' : '✗'} ${msg}`); if (!ok) failed = true; };
gate(blendLeft === 0, `0 BLEND-матеріалів (маємо ${blendLeft})`);
gate(bytes <= 2.0 * 1048576, `розмір ≤ 2.0 MB (маємо ${(bytes / 1048576).toFixed(2)} MB)`);
gate(trisAfter === trisBefore, `геометрія не втрачена (${trisBefore} → ${trisAfter})`);
// Меші/ноди мають лишитись усі. Кількість МАТЕРІАЛІВ може легітимно впасти: dedup зливає
// лише побайтово ідентичні. У цій моделі ArchiCAD віддав 2 дублікати під різними іменами
// («Металл-Нержавеющая сталь» ≡ «Металл - Сталь Нержавеющая», «Краска-04» ≡ інша фарба).
// Обидва були OPAQUE ще в джерелі ⇒ до фіксу alphaMode це відношення не має. 38→36 — норма.
gate(root.listMeshes().length === 38, `38 мешів збережено (маємо ${root.listMeshes().length})`);
gate(root.listMaterials().length >= 36, `матеріали не втрачені понад дублікати (маємо ${root.listMaterials().length}/38)`);
gate(root.listTextures().length === 15, `15 текстур (маємо ${root.listTextures().length})`);
gate(root.listMeshes().every((m) => m.listPrimitives().every((p) => p.getMaterial())),
  'кожен меш має матеріал');
process.exit(failed ? 1 : 0);

function countTris(root) {
  let t = 0;
  for (const mesh of root.listMeshes())
    for (const prim of mesh.listPrimitives()) {
      const idx = prim.getIndices();
      t += idx ? idx.getCount() / 3 : prim.getAttribute('POSITION').getCount() / 3;
    }
  return t;
}
