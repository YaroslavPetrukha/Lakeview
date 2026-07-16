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
import { statSync, renameSync, unlinkSync } from 'node:fs';

const [, , inPath = 'новий концепт/Квартира.glb', outPath = 'img/3d/kv-b21.glb'] = process.argv;

/**
 * Скло. Експорт переплутав усе навпаки: бетон/паркет/штукатурка приїхали BLEND,
 * а СКЛО — OPAQUE, opacity 1, roughness 0.9. Тобто скління тераси рендериться
 * матовим сіро-блакитним пластиком і замуровує головну перевагу квартири —
 * терасу й денне світло. Перевірено рейкастом у реальному Chrome: промінь із
 * вітальні до тераси впирався в «Стекло - Голубое» за 2.89 м.
 * Значення підібрані візуально в реальному Chrome (скління пліковане, промінь
 * ловить 3 шари на 2.89/2.97/3.01 м — тому низька непрозорість, інакше серпанок).
 */
const GLASS = /скло|стекло|glass/i;
const GLASS_ALPHA = 0.09;

const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(inPath);
const root = doc.getRoot();

// ── 1. alphaMode: виправити ОБИДВІ помилки експорту ─────────────────────────
// Класифікація за назвою матеріалу — крихка: скло, назване інакше («шкло»,
// «vitrage», друкарська помилка), поїде в else-гілку й стане матовим пластиком,
// повернувши саме той баг, який цей скрипт лікує. Тому логуємо КОЖЕН
// перекласифікований матеріал — щоб людина оком звірила після реекспорту.
let fixed = 0, glassFixed = 0;
const reclassified = [];
for (const mat of root.listMaterials()) {
  const name = mat.getName() || '(unnamed)';
  if (GLASS.test(name)) {
    // OPAQUE → справжнє скло. Власний відтінок кожного скла ЗБЕРІГАЄМО:
    // просто підмішуємо його до світлого й ставимо альфу. Якщо задати обом
    // однаковий колір — dedup зіллє їх в один і зітре задум архітектора
    // («Стекло - Голубое» #a0acb6 і темніше «Стекло голубое» #517180).
    const [r, g, b] = mat.getBaseColorFactor();
    mat.setAlphaMode('BLEND');
    mat.setAlpha(GLASS_ALPHA);
    mat.setRoughnessFactor(0.02);
    mat.setMetallicFactor(0);
    mat.setBaseColorFactor([
      Math.min(1, r * 0.35 + 0.65), Math.min(1, g * 0.35 + 0.65), Math.min(1, b * 0.35 + 0.68),
      GLASS_ALPHA,
    ]);
    glassFixed++;
    reclassified.push(`  скло   → прозоре : ${name}`);
  } else if (mat.getAlphaMode() === 'BLEND') {
    // BLEND → OPAQUE (доведено: жодного невидимого пікселя в текстурі)
    mat.setAlphaMode('OPAQUE');
    mat.setAlpha(1.0);
    fixed++;
    reclassified.push(`  BLEND  → opaque  : ${name}`);
  }
}
console.log(`alphaMode BLEND→OPAQUE: ${fixed} матеріалів`);
console.log(`скло OPAQUE→прозоре:   ${glassFixed} матеріалів`);
console.log('перекласифіковано (звірити оком після реекспорту):');
for (const line of reclassified) console.log(line);

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
  // q90, не q82: попіксельне порівняння показало, що q82 просаджував текстури ПІДЛОГИ
  // (ламінат/паркет) до PSNR 37 dB — а на підлогу в прогулянці дивишся постійно.
  // q90 піднімає їх до ~41 dB (візуально без втрат) і лишається 1.91 MB (< 2 MB).
  // Вище не йдемо: q95 = 2.03 MB перевищує бюджет, а «Грунт» тераси все одно впирається
  // у ~28 dB через власний шум — то не WebP, і гнатися нема за чим.
  textureCompress({ encoder: sharp, targetFormat: 'webp', quality: 90, resize: [1024, 1024] }),
);
const trisAfter = countTris(root);

// Пишемо в ТИМЧАСОВИЙ файл. Гейти мають ЗАХИЩАТИ, а не лише звітувати: якщо
// записати одразу в outPath, «провалений» гейт нічому не завадить — зламаний
// актив уже лежить у img/3d/ готовий до деплою. Тому rename в outPath — тільки
// після проходження всіх гейтів (fail-closed).
// ⚠️ temp-шлях МУСИТЬ закінчуватись на .glb: gltf-transform обирає формат за
// розширенням, і будь-що інше (.tmp) пише glTF-JSON БЕЗ бінарного буфера —
// зламаний 70 КБ файл, який гейти по пам'яті не помітять.
const tmpPath = outPath.replace(/\.glb$/i, '.building.glb');
await io.write(tmpPath, doc);

// ── 4. Gates ───────────────────────────────────────────────────────────────
// Round-trip: перечитуємо те, що реально записали — ловить зіпсований/непарсабельний GLB.
let roundTrip = true, roundTripErr = '';
try { await new NodeIO().registerExtensions(ALL_EXTENSIONS).read(tmpPath); }
catch (e) { roundTrip = false; roundTripErr = e.message; }

const blendLeft = root.listMaterials()
  .filter((m) => m.getAlphaMode() === 'BLEND' && !GLASS.test(m.getName() || '')).length;
const glassOpaque = root.listMaterials()
  .filter((m) => GLASS.test(m.getName() || '') && m.getAlphaMode() === 'OPAQUE').length;
const bytes = statSync(tmpPath).size;
const srcBytes = statSync(inPath).size;

console.log(`\nтрикутники: ${trisBefore.toLocaleString()} → ${trisAfter.toLocaleString()}`);
console.log(`розмір:     ${(srcBytes / 1048576).toFixed(2)} MB → ${(bytes / 1048576).toFixed(2)} MB (−${(100 - (bytes / srcBytes) * 100).toFixed(0)}%)`);
console.log(`меші/матеріали/текстури: ${root.listMeshes().length} / ${root.listMaterials().length} / ${root.listTextures().length}`);

let failed = false;
const gate = (ok, msg) => { console.log(`${ok ? '✓' : '✗'} ${msg}`); if (!ok) failed = true; };
// Гейти виражають ІНВАРІАНТИ, а не точні числа цієї ревізії — інакше наступний
// реекспорт архітектора (37 мешів, 3 скла) провалить збірку без реального дефекту.
gate(roundTrip, `вихідний GLB перечитується${roundTrip ? '' : ` (${roundTripErr})`}`);
gate(blendLeft === 0, `0 хибно-прозорих матеріалів (маємо ${blendLeft})`);
gate(glassOpaque === 0, `жодне скло не лишилось матовим (маємо ${glassOpaque})`);
gate(bytes <= 2.0 * 1048576, `розмір ≤ 2.0 MB (маємо ${(bytes / 1048576).toFixed(2)} MB)`);
// Нижня межа ловить «безтекстурний» вихід (напр. запис у не-.glb): 15 вбудованих
// текстур не можуть важити менше ~0.25 MB. Гейти по пам'яті такого не бачать.
gate(bytes >= 0.25 * 1048576, `текстури вбудовані — розмір ≥ 0.25 MB (маємо ${(bytes / 1048576).toFixed(2)} MB)`);
gate(trisAfter <= trisBefore, `геометрія не роздута (${trisBefore} → ${trisAfter})`);
gate(root.listMeshes().length >= 1, `є меші (${root.listMeshes().length})`);
gate(root.listTextures().length >= 1, `є текстури (${root.listTextures().length})`);
// Найзмістовніший гейт: жоден меш не лишився без матеріалу (→ magenta в рантаймі).
gate(root.listMeshes().every((m) => m.listPrimitives().every((p) => p.getMaterial())),
  'кожен меш має матеріал');

if (failed) {
  unlinkSync(tmpPath);
  console.error('\n✗ гейти не пройдено — актив НЕ записано (старий img/3d/kv-b21.glb недоторканий)');
  process.exit(1);
}
renameSync(tmpPath, outPath);
console.log(`\n✓ усі гейти пройдено → ${outPath}`);
process.exit(0);

function countTris(root) {
  let t = 0;
  for (const mesh of root.listMeshes())
    for (const prim of mesh.listPrimitives()) {
      const idx = prim.getIndices();
      t += idx ? idx.getCount() / 3 : prim.getAttribute('POSITION').getCount() / 3;
    }
  return t;
}
