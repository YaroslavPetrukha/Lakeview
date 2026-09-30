# GTM-контейнер Lakeview (GTM-NMZFC3XN)

Файл імпорту: `tools/gtm/lakeview-gtm-container.json` (формат експорту GTM, `exportFormatVersion: 2`).

Контейнер лише читає події, які сайт уже пушить у `dataLayer` (`index.html`, функції `_track()` і `_submitForm()`). Код сайту для роботи контейнера міняти не треба.

## Що всередині

### Теги

| Тег | Тип | Тригер | Що робить |
|---|---|---|---|
| GA4 - Config (Google tag) | Google tag (`googtag`) | Initialization - All Pages | Завантажує GA4 `G-YLEXBZ88BW`, шле `page_view`. Розширені вимірювання (скрол, вихідні кліки тощо) налаштовані в самому GA4. |
| GA4 - Event - generate_lead | GA4 Event | CE - generate_lead | Заявка. Параметри: `form_id`, `form_place`, `event_id`. Це подія, яку позначаємо ключовою і яку імпортує Google Ads. |
| GA4 - Event - phone_click | GA4 Event | CE - phone_click | Тап по `tel:`. Параметр `link_location`. |
| GA4 - Event - social_click | GA4 Event | CE - social_click | Клік на Instagram / Facebook / Telegram / Viber / WhatsApp. Параметри `link_url`, `link_location`. |
| GA4 - Event - plan_open | GA4 Event | CE - plan_open | Відкриття збільшеного планування. Параметр `plan`. |
| Google Ads - Conversion Linker | Conversion Linker | All Pages | Зберігає `gclid` у first-party cookie `_gcl_aw`, щоб Google Ads зіставляв конверсії з кліками. |
| Meta - Pixel - Base (PageView) | Custom HTML | All Pages, **Once per page** | Ініціалізує Pixel `1109538811421547`, шле `PageView`. Має захист від повторної ініціалізації. Автоматичні події Meta вимкнено (`autoConfig false`). Розширене зіставлення (advanced matching) не використовується. |
| Meta - Pixel - Lead | Custom HTML | CE - generate_lead | `Lead` з `eventID` = `event_id` з dataLayer. Server-side CAPI в `api/submit.php` шле такий самий `Lead` з тим самим `event_id`, тож Meta рахує заявку **один раз**. Спочатку спрацьовує тег Base (tag sequencing). |
| Meta - Pixel - PhoneClick (custom) | Custom HTML | CE - phone_click | **Кастомна** подія `PhoneClick`, а не стандартна `Contact`. Стандартну `Contact` можна випадково обрати подією оптимізації в оголошенні, а тап по номеру ще не означає заявку. `PhoneClick` підходить лише для аудиторій і для custom conversion, якщо її створити свідомо. |

Тег конверсій Google Ads **навмисно відсутній**: конверсію імпортуємо з GA4 (`generate_lead`). Якщо додати ще й тег Ads, заявка порахується двічі.

### Тригери

| Тригер | Умова |
|---|---|
| CE - generate_lead | Подія `generate_lead` **і** `event_id` має формат UUID **і** хост `lakeview.com.ua` / `www.lakeview.com.ua`. Додаткові фільтри не пропускають тестові пуші з консолі, пуші з дзеркал і з localhost, а також Lead без `eventID`, який Meta не змогла б дедуплікувати. |
| CE - phone_click | Подія `phone_click` |
| CE - social_click | Подія `social_click` |
| CE - plan_open | Подія `plan_open` |

### Змінні

- `Const - GA4 Measurement ID` = `G-YLEXBZ88BW`
- `Const - Meta Pixel ID` = `1109538811421547`
- Змінні шару даних (Data Layer Variables, v2): `DLV - form_id`, `DLV - form_place`, `DLV - event_id`, `DLV - link_location`, `DLV - link_url`, `DLV - plan`
- Вбудовані змінні (вмикаються імпортом): Page URL, Page Hostname, Page Path, Referrer, Event, Container ID, HTML ID. Тег Lead використовує Container ID і HTML ID, щоб повідомити GTM про завершення лише через 300 мс після відправлення Pixel і запит встиг піти до переходу на `/thanks.html`.

## Чому без `value` / `currency` у generate_lead

Надійної цінності заявки поки немає: заявка на комерцію і на однокімнатну квартиру коштують зовсім по-різному, а даних CRM про конверсію в угоду ще немає. Якщо передавати вигадану суму, Google Ads і Meta почнуть оптимізувати на хибну цінність. На старті стратегія ставок — «Максимум конверсій» або tCPA, їм цінність не потрібна. Коли з CRM з'явиться частка угод за `form_place`, можна додати таблицю підстановки (Lookup Table) `form_place → value` і параметри `value` + `currency: USD`.

## Імпорт

1. GTM → **Admin** → **Import Container**.
2. Файл: `lakeview-gtm-container.json`.
3. Workspace: **Existing** → Default Workspace (або новий, наприклад «Launch 2026-10»).
4. Режим: **Merge** → **Rename conflicting tags, triggers, and variables**. Контейнер порожній, тож конфліктів не буде.
5. Перевірити попередній перегляд імпорту: 9 тегів, 4 тригери, 8 змінних, 7 вбудованих змінних → **Confirm**.
6. Ще **не публікувати**: спершу пройти перевірку нижче.

## Перевірка

### GTM Preview / Tag Assistant
1. **Preview** → `https://www.lakeview.com.ua/`.
2. На *Container Loaded* / *Initialization* має спрацювати `GA4 - Config`. На *Container Loaded* — `Conversion Linker` і `Meta - Pixel - Base`.
3. Клік на телефон (header / мобільна кнопка) → `phone_click`: спрацьовують `GA4 - Event - phone_click` і `Meta - Pixel - PhoneClick`, у Variables видно `link_location`.
4. Відкрити планування → `plan_open` → `GA4 - Event - plan_open`.
5. **Справжня тестова заявка** (позначити в Telegram-групі як тест): подія `generate_lead` → `GA4 - Event - generate_lead` і `Meta - Pixel - Lead` зі статусом *Succeeded*. У Variables `DLV - event_id` має бути UUID.
6. Відправити форму з консолі без справжнього `event_id` (`dataLayer.push({event:'generate_lead'})`) → теги **не** мають спрацювати.

### GA4 DebugView
Admin → DebugView. Коли відкрито Tag Assistant, події приходять разом із `debug_mode`. Перевірити параметри `generate_lead`.

### Meta Events Manager → Test Events
1. Events Manager → Pixel `1109538811421547` → **Test events**. Скопіювати test code і тимчасово вписати його в `META_TEST_EVENT_CODE` в `api/config.php` на сервері.
2. Відкрити сайт з вкладки Test events і відправити тестову заявку.
3. Мають з'явитися `PageView` (Browser), `Lead` (Browser) **і** `Lead` (Server) з однаковим Event ID, а біля події — позначка **Deduplicated** / «Processed: 1 of 2».
4. **Прибрати `META_TEST_EVENT_CODE` після тесту**, інакше серверні Lead не підуть у бойову статистику.
5. Meta Pixel Helper (розширення Chrome): один Pixel ID, один PageView, без попереджень «multiple pixels / duplicate».

## GA4: що налаштувати після публікації

- **Admin → Events → Key events**: позначити `generate_lead` (метод підрахунку — *Once per event*). `phone_click` ключовою подією **не** робити: тап по `tel:` на десктопі нічого не означає, а дзвінки рахуватиме Бінотел (CRM #76).
- **Admin → Custom definitions** → Custom dimensions (Event scope): `form_id`, `form_place`, `link_location`, `plan`. `event_id` **не реєструвати**: у кожної заявки унікальне значення, звіт одразу впреться в «(other)».
- Google Ads → Goals → Conversions → Import → GA4 → `generate_lead` (Web): **Primary**, Count = **One**, вікно 30–90 днів. Інші імпортовані події, якщо з'являться, — лише **Secondary**.
- GA4 → Data streams → Configure tag settings → **Define internal traffic** (IP офісу) + Data filter, щоб тести команди не йшли в звіти.

## Згода на cookies (Consent Mode) — пізніше

Зараз банера немає, тому в тегах стоїть `Consent: Not set`. Коли з'явиться банер:
1. Додати тег Consent Mode default (`ad_storage`, `analytics_storage`, `ad_user_data`, `ad_personalization` = denied) на тригері **Consent Initialization - All Pages**. Тригер уже зарезервований у GTM, конфліктів не буде.
2. Google tag і Conversion Linker мають вбудовану перевірку згоди, їх міняти не треба.
3. Трьом тегам Meta поставити *Additional consent checks* → `ad_storage` (і `ad_user_data`), бо сам Pixel Consent Mode не розуміє.
4. Server-side CAPI в `submit.php` при цьому теж має враховувати згоду (передавати її з форми).
