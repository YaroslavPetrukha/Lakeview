# BIMx квартири Кв В-2.1 → сайт: рішення (дослідження 2026-07-13)

Файл: `новий концепт/Квартира_Володимира Великого.bimx` (3.1 MB, `BIMxQLZ`, ArchiCAD 21).

## Головне
**Сирий `.bimx` на сайт напряму не йде** — пропрієтарний контейнер Graphisoft, відкритого парсера нема (GitHub перевірено; «bimx-конвертери» онлайн — ненадійні, ще й ризик злити модель клієнта). Не колупаємо `.bimx` — беремо свіжий експорт із `.pln`.

## Ранжування

| # | Шлях | Якість | Зусилля | Ціна | Статичний сайт | Вердикт |
|---|------|--------|---------|------|----------------|---------|
| 1 | **BIMx Web Viewer iframe** (офіційний) | Висока, нативний рендер+навігація | ~0: архітектор вантажить, я вставляю iframe | Free (public) | Ідеально | **Зробити першим** |
| 2 | **ArchiCAD→GLB → `<model-viewer>`/three.js** (самохост) | Висока, повний контроль/бренд | Помірне: архітектор експортує GLB | 0–€19 | Ідеально | **Найкраще для нашого стеку** |
| 3 | ArchiCAD→IFC → xeokit/ThatOpen | Добра, але «технічний» BIM-вигляд | Вище (IFC→XKT) | Free | Добре | Надмір для 1 квартири |
| 4 | Speckle (конектор ArchiCAD → iframe) | Добра | Низьке-помірне | Free tier / $99 | Добре | Хмарна залежність |
| 5 | 360° панорама (Pannellum/Marzipano) | Фотореал, але фікс-точки | Низьке | Free | Ідеально | Легкий фолбек (у нас є рендери) |
| 6 | Autodesk APS/Forge | Висока | Високе, **потрібен бекенд-токен** | Платно | Погано | Reject (ламає «no backend») |
| — | Прямий парс `.bimx` | — | Неможливо | — | — | Reject |

## ✅ ВИПРАВЛЕННЯ 2026-07-13: BIMx РЕНДЕРИТЬСЯ ІДЕАЛЬНО — вбудовано
Мій попередній висновок «пурпур/без текстур» був **ХИБНИЙ** — це артефакт **headless-браузера Playwright (без GPU, не декодує стиснуті текстури)**. На реальному Chrome у Ярослава модель повністю текстурована (паркет, плитка, меблі, рослини, тераса) — виглядає чудово (пруф-скрін від клієнта).
**Урок:** BIMx-візуал НЕ верифікувати в Playwright — тільки реальний браузер.

**Вбудовано:** грань «Квартира» hero-3d.html → `openApartmentTour()` → оверлей-iframe з `TOUR_URL='https://bimx.graphisoft.com/model/4a84348f-3784-4a64-898b-552ff2a30ecb'` + кнопка ×/ESC. Наскрізно перевірено (open/close). Заголовки Graphisoft **без X-Frame-Options/frame-ancestors** → фреймінг дозволено.
Нюанси: model-page URL відкриває **лендінг з play** (не одразу 3D) → тому `TOUR_URL` = **прямий viewer-URL** (`bimx-webviewer.graphisoft.com/?modelId=...&auth=<JWT>`) — відкривається ОДРАЗУ у 3D-обліт. ⚠ **Токен `auth` живе ~24 год** → лінк протухне. Сталі варіанти (для прод):
- **«Embed Hyper-model» сніпет** з BIMx (на сторінці моделі, залогіненим власником — іконка embed/`</>`; дає durable chrome-less viewer) → підставити в `TOUR_URL`;
- **self-host GLB** у наш three.js/`<model-viewer>` (найнадійніше, on-brand, без токенів/залежності);
- (крайній) PHP-проксі, що мінтить свіжий токен per-load (наш хостинг має PHP) — але крихко/скрейп.
Параметричний тур лишається фолбеком (`apartment-tour.html`).

## ⚠️ (застаріле) Апдейт: Ярослав залив BIMx (public) — про «пурпур» див. виправлення вище
Модель: `bimx.graphisoft.com/model/4a84348f-3784-4a64-898b-552ff2a30ecb`, видимість — **Публічна**.
Перевірено інтерактивний BIMx Web Viewer (`bimx-webviewer.graphisoft.com/?modelId=...&auth=<JWT>`):
- Viewer **працює й інтерактивний** (Hyper-model Index → 3D, навігація). ✅
- **АЛЕ модель БЕЗ ТЕКСТУР** — пурпурово-картатий «missing texture» на всіх поверхнях. ❌ (експорт залив геометрію без матеріалів; те саме було в карвлених прев'ю.)
- Токен `auth` у viewer-URL **живе 24 год** (exp−iat=86400) → сирий URL зашивати не можна; для сталого embed потрібен саме сніпет з «Embed Hyper-model».
**Висновок:** зараз НЕ вбудовуємо цю BIMx у грань «Квартира» (виглядатиме гірше за наш чистий параметричний тур). Треба:
1. **Пере-експорт BIMx із увімкненими текстурами** (в ArchiCAD BIMx-publish: включити текстури/матеріали), АБО
2. краще — **GLB з вбудованими текстурами** → self-host → `loadApartmentModel('/img/3d/apartment.glb')` (повний контроль, без magenta, без токен-експірації).
Прев'ю проблеми: `concept/preview/bimx-webviewer-magenta.png`.

## Рекомендація
**Обидва:** (A) BIMx iframe — щоб миттєво показати реальну модель; (B) самохост GLB — для брендованої інтеграції в наш уже готовий three.js-тур (`window.loadApartmentModel('/img/3d/apartment.glb')`).

### A — BIMx Web (сьогодні, ~15 хв)
Архітектор: free Graphisoft ID → вантажить `.bimx` на bimx.graphisoft.com (public, 5 GB free) → «Embed Hyper-model» → дає iframe-сніпет. Я вставляю в адаптивний контейнер.
⚠️ Free public = модель публічна й завантажувана + чром Graphisoft. Приватний (non-download) embed = платний SSA/Forward.

### B — самохост GLB → `<model-viewer>` (наш стек, on-brand)
Архітектор дає **`.glb` з вбудованими текстурами** (плагін **Bimdots glTF Out** €0–19, але **лише AC26–29** — а файл AC21!; фолбеки: Okino PolyTrans, або IFC-шлях, або FBX/OBJ→GLB через `gltf-transform`). Стиснути: `npx @gltf-transform/cli optimize in.glb out.glb --texture-compress webp` (Draco+WebP, ціль <8–15 MB). Хостимо `/img/3d/apartment.glb`, `<model-viewer>` (Apache-2.0, без бекенду) або наш three.js GLTFLoader.

## Що попросити в архітектора (samila_design) — одне з:
1. **BIMx share/embed-лінк** (найшвидше), **або**
2. **`.glb`** з вбудованими текстурами (найкраще), **або**
3. **`.ifc`** (фолбек, будь-яка версія AC), **або**
4. кілька **360° equirectangular рендерів** (легкий тур).
**Ідеальний запит:** «GLB із вбудованими текстурами + BIMx web-лінк як інтерим».

Джерела: graphisoft.com/pulse/publish-your-bimx-model-directly-to-a-website · bimx.graphisoft.com · bimdots.com/product/gltf-out · speckle.systems/connectors/archicad · xeokit.io · github.com/ThatOpen/web-ifc-viewer · pannellum.org
