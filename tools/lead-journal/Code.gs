/**
 * Журнал лідів ЖК Lakeview — окремий Apps Script-проєкт, що пише в Google-таблицю.
 *
 * api/submit.php після кожної справжньої заявки шле сюди POST з JSON (у фоні,
 * після відповіді браузеру). Скрипт дописує рядок на аркуш «Ліди». Колонки
 * A–U пише скрипт, V–AA заповнює відділ продажу вручну.
 *
 * Налаштування (один раз):
 *   1. script.google.com → Новий проєкт (під власником таблиці) → вставити цей файл.
 *      (Не «Розширення → Apps Script»: при кількох Google-логінах у браузері він
 *      відкривається під чужим акаунтом.)
 *   2. Налаштування проєкту → Властивості скрипта:
 *      SHEET_ID       = ID таблиці з її адреси (/spreadsheets/d/<ID>/edit);
 *      WEBHOOK_SECRET = той самий рядок, що LEAD_SHEET_WEBHOOK_SECRET в api/config.php.
 *   3. Запустити setupSchema() вручну (лише на порожній таблиці).
 *   4. Ввести в дію → Веб-застосунок → Виконувати як: я; Доступ: усі.
 *      Після правки коду: «Керувати введеннями в дію» → олівець → «Нова версія»
 *      (НЕ нове розгортання — інакше зміниться /exec-адреса).
 */

var SHEET_NAME = 'Ліди';

var HEADERS = [
  'Дата і час (Київ)', 'Канал', 'Форма', 'Місце форми', "Ім'я", 'Телефон',
  'Месенджер', 'Квартира / приміщення', 'Тип бізнесу', 'Пристрій',
  'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
  'gclid', 'gbraid', 'wbraid', 'fbclid', 'Сторінка', 'lead_id',
  // ── далі вручну ──
  'Статус', 'Причина відмови', 'Менеджер', 'Наступний крок (дата)', 'Сума угоди, $', 'Коментар'
];
var AUTO_COLS = 21;   // A–U пише скрипт
var PHONE_COL = 6;    // F

var STATUSES = [
  'Нова', 'В роботі', 'Не додзвонились', 'Консультація', 'Показ призначено',
  'Показ відбувся', 'Бронь', 'Угода', 'Відмова', 'Нецільовий / спам', 'Дубль'
];
var REASONS = [
  'Ціна', 'Планування / площа', 'Строк здачі', 'Локація', 'Умови оплати',
  'Купив інше', 'Не на часі', 'Не відповідає', 'Інше'
];

/** Запускати вручну один раз на порожній таблиці. */
function setupSchema() {
  var ss = book_();
  var sh = ss.getSheetByName(SHEET_NAME) || ss.getSheets()[0].setName(SHEET_NAME);
  if (sh.getLastRow() > 1) throw new Error('На аркуші вже є дані — setupSchema лише для порожньої таблиці');

  sh.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS])
    .setFontWeight('bold').setBackground('#0F4C3A').setFontColor('#ffffff').setWrap(true);
  sh.getRange(1, AUTO_COLS + 1, 1, HEADERS.length - AUTO_COLS).setBackground('#C5A55A').setFontColor('#000000');
  sh.setFrozenRows(1);
  sh.setFrozenColumns(1);

  var max = sh.getMaxRows();
  sh.getRange(2, PHONE_COL, max - 1, 1).setNumberFormat('@');
  sh.getRange(2, AUTO_COLS + 1, max - 1, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(STATUSES, true).setAllowInvalid(false).build());
  sh.getRange(2, AUTO_COLS + 2, max - 1, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(REASONS, true).setAllowInvalid(true).build());
  sh.getRange(2, AUTO_COLS + 4, max - 1, 1).setNumberFormat('dd.mm.yyyy').setDataValidation(
    SpreadsheetApp.newDataValidation().requireDate().setAllowInvalid(false).build());
  sh.getRange(2, AUTO_COLS + 5, max - 1, 1).setNumberFormat('#,##0');

  // Колонки трекінгу (K–U) рідко потрібні менеджеру — групою, щоб згорнути.
  sh.getRange(1, 11, 1, 11).shiftColumnGroupDepth(1);

  sh.setColumnWidth(1, 140);
  sh.setColumnWidth(3, 170);
  sh.setColumnWidth(5, 140);
  sh.setColumnWidth(6, 130);
  sh.setColumnWidth(8, 180);
  sh.setColumnWidth(AUTO_COLS + 1, 140);
  sh.setColumnWidth(AUTO_COLS + 2, 150);
  sh.setColumnWidth(HEADERS.length, 300);
}

function doPost(e) {
  var d;
  try {
    d = JSON.parse(e.postData.contents);
  } catch (err) {
    return out_('bad-json');
  }
  var secret = PropertiesService.getScriptProperties().getProperty('WEBHOOK_SECRET');
  if (!secret || d.secret !== secret) return out_('forbidden');

  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var sh = book_().getSheetByName(SHEET_NAME);
    var row = [
      d.time, 'форма', d.form, d.form_place, d.name, '',
      d.messenger, d.apartment, d.biz_type, d.device,
      d.utm_source, d.utm_medium, d.utm_campaign, d.utm_content, d.utm_term,
      d.gclid, d.gbraid, d.wbraid, d.fbclid, d.page, d.lead_id
    ].map(safe_);
    sh.appendRow(row);
    var r = sh.getLastRow();
    // Телефон окремо: у appendRow провідний «+» Sheets читає як формулу і з'їдає.
    if (d.phone) {
      sh.getRange(r, PHONE_COL).setNumberFormat('@').setValue('+' + String(d.phone).replace(/\D/g, ''));
    }
    sh.getRange(r, AUTO_COLS + 1).setValue('Нова');
  } finally {
    lock.releaseLock();
  }
  return out_('ok');
}

function book_() {
  return SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('SHEET_ID'));
}

function doGet() {
  return out_('alive');
}

/** Текст від відвідувача ніколи не стає формулою (=, +, -, @ на початку). */
function safe_(v) {
  if (v === undefined || v === null) return '';
  var s = String(v);
  return /^[=+\-@]/.test(s) ? "'" + s : s;
}

function out_(msg) {
  return ContentService.createTextOutput(msg);
}
