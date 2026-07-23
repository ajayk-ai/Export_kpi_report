/**************************************************************
 * Country Filter Link
 *
 * Lets the KPI email's "Over Due Breakup" numbers deep-link into
 * this spreadsheet, pre-filtered to that one country AND to the same
 * "over due" rows the email counted, without disturbing what any
 * other viewer currently has filtered (each click gets its own
 * Filter View instead of touching the shared Basic Filter).
 *
 * The overdue rule below (isOverdueRow_) must stay in lockstep with
 * KPI 3 ("Over Due Breakup") in app/core/kpi_engine.py
 * (compute_country_breakup -> overdue_breakup). If that Python logic
 * changes, mirror the change here too, or the emailed count and the
 * filtered sheet will silently disagree again.
 *
 * Setup:
 *   1. Extensions > Apps Script > Services (+) > add "Google Sheets API"
 *      (the Advanced Service; also enable it in the linked GCP project
 *      if prompted).
 *   2. Add this file to the same Apps Script project as the existing
 *      onEdit script (File > New > Script file).
 *   3. Deploy > New deployment > type: Web app.
 *      Execute as: Me. Who has access: Anyone with the link.
 *   4. Copy the resulting /exec URL into .env as FILTER_WEBAPP_URL.
 **************************************************************/

var FILTER_TAB_NAME = "SCM_Export_Orders"; // must match WORKSHEET_NAME in .env
var FILTER_COLUMN_HEADER = "Country";

// Column headers the overdue rule reads from — must match kpi_engine.py's
// COL_LOADING_DATE / COL_MACHINE_REVISION / COL_MACHINE_READINESS exactly.
var OVERDUE_COL_LOADING = "Loading (Dispatched) Date";
var OVERDUE_COL_REVISION = "production commitment Revise Date";
var OVERDUE_COL_READINESS = "production commitment Date";

// Hidden working column this script writes TRUE/FALSE into so the Filter
// View criteria (which can only test column values, not arbitrary formulas)
// can select exactly the overdue rows. Recomputed fresh on every click.
var OVERDUE_HELPER_HEADER = "_OverDueFilterFlag";

function doGet(e) {
  // `e` is only populated on a real HTTP request to the deployed /exec URL.
  // Clicking "Run" on doGet directly in the editor calls it with no
  // arguments at all, so guard `e` itself, not just `e.parameter` — see the
  // test_* functions below for how to exercise this from the editor instead.
  var country = ((e && e.parameter && e.parameter.country) || "").trim();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(FILTER_TAB_NAME);

  if (!country) {
    return HtmlService.createHtmlOutput("Missing 'country' parameter.");
  }
  if (!sheet) {
    return HtmlService.createHtmlOutput(
      "Tab '" + FILTER_TAB_NAME + "' not found."
    );
  }

  var fvid;
  try {
    fvid = getOrCreateFilterView(ss, sheet, country);
  } catch (err) {
    return HtmlService.createHtmlOutput(
      "Could not build filter view: " + escapeHtml(err.message)
    );
  }

  var url =
    "https://docs.google.com/spreadsheets/d/" +
    ss.getId() +
    "/edit#gid=" +
    sheet.getSheetId() +
    "&fvid=" +
    fvid;

  // Google serves domain-restricted Web App URLs (script.google.com/a/macros/...)
  // inside a sandboxed frame that blocks JS from navigating the top window, so
  // an automatic redirect silently fails there. A target="_top" link is the one
  // navigation method that sandbox still allows, so we show a button instead.
  var html =
    "<div style='font-family:Arial,sans-serif;padding:32px;text-align:center;'>" +
    "<p style='font-size:15px;color:#333;'>Filtered view ready for <b>" +
    escapeHtml(country) +
    "</b>.</p>" +
    "<p><a href=" +
    JSON.stringify(url) +
    " target='_top' rel='noopener' style='display:inline-block;padding:12px 22px;" +
    "background:#1a73e8;color:#fff;text-decoration:none;border-radius:6px;" +
    "font-weight:600;font-size:14px;'>Open filtered sheet</a></p>" +
    "</div>";

  return HtmlService.createHtmlOutput(html).setXFrameOptionsMode(
    HtmlService.XFrameOptionsMode.ALLOWALL
  );
}

/**
 * Returns the filterViewId for `country` on `sheet`, filtered to both that
 * country AND the current overdue rows. Reuses the view from a previous
 * click (id cached in Script Properties) as long as it still exists;
 * otherwise creates a fresh one via the Sheets Advanced Service.
 *
 * The helper column is refreshed unconditionally, even on a cache hit —
 * Filter View criteria re-evaluates against current cell values every time
 * it's opened, so a reused view only stays correct if the helper column
 * it points at is kept up to date with today's date and the latest data.
 */
function getOrCreateFilterView(ss, sheet, country) {
  var props = PropertiesService.getScriptProperties();
  var key = "fvid:" + sheet.getSheetId() + ":" + country;
  var cached = props.getProperty(key);
  var existingIds = listFilterViewIds(ss, sheet.getSheetId());

  var helperColIndex = refreshOverdueHelperColumn_(sheet);

  if (cached && existingIds[cached]) {
    return cached;
  }

  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var colIndex = findColumnIndex_(headers, FILTER_COLUMN_HEADER);
  if (colIndex === -1) {
    throw new Error(
      "Column '" + FILTER_COLUMN_HEADER + "' not found in " + FILTER_TAB_NAME
    );
  }

  var criteria = {};
  criteria[colIndex] = {
    condition: {
      type: "TEXT_EQ",
      values: [{ userEnteredValue: country }]
    }
  };
  criteria[helperColIndex] = {
    condition: {
      type: "TEXT_EQ",
      values: [{ userEnteredValue: "TRUE" }]
    }
  };

  var request = {
    requests: [
      {
        addFilterView: {
          filter: {
            title: "Country: " + country,
            range: {
              sheetId: sheet.getSheetId(),
              startRowIndex: 0,
              startColumnIndex: 0,
              endColumnIndex: Math.max(headers.length, helperColIndex + 1)
            },
            criteria: criteria
          }
        }
      }
    ]
  };

  var response = Sheets.Spreadsheets.batchUpdate(request, ss.getId());
  var fvid = String(response.replies[0].addFilterView.filter.filterViewId);
  props.setProperty(key, fvid);
  return fvid;
}

/**
 * Recomputes the hidden "_OverDueFilterFlag" column against the sheet's
 * CURRENT data and returns its 0-based column index. Writes "TRUE"/"FALSE"
 * per row using the same rule as KPI 3 in kpi_engine.py (see isOverdueRow_).
 *
 * Reuses the existing helper column if one is already present (matched by
 * header text) instead of appending a new one on every click; a pipeline
 * run that overwrites the whole worksheet (see overwrite_worksheet in
 * app/clients/sheets_client.py) wipes it along with everything else, so it
 * gets recreated at the next click either way.
 */
function refreshOverdueHelperColumn_(sheet) {
  var lastColumn = sheet.getLastColumn();
  var lastRow = sheet.getLastRow();
  var headers = sheet.getRange(1, 1, 1, lastColumn).getValues()[0];

  var colLoading = findColumnIndex_(headers, OVERDUE_COL_LOADING);
  var colRevision = findColumnIndex_(headers, OVERDUE_COL_REVISION);
  var colReadiness = findColumnIndex_(headers, OVERDUE_COL_READINESS);
  var missing = [];
  if (colLoading === -1) missing.push(OVERDUE_COL_LOADING);
  if (colRevision === -1) missing.push(OVERDUE_COL_REVISION);
  if (colReadiness === -1) missing.push(OVERDUE_COL_READINESS);
  if (missing.length) {
    throw new Error(
      "Column(s) not found for overdue filtering: " + missing.join(", ")
    );
  }

  var existingHelperCol = findColumnIndex_(headers, OVERDUE_HELPER_HEADER);
  var helperColumn1Based = existingHelperCol === -1 ? lastColumn + 1 : existingHelperCol + 1;

  sheet.getRange(1, helperColumn1Based).setValue(OVERDUE_HELPER_HEADER);

  if (lastRow >= 2) {
    var rowCount = lastRow - 1;
    var loadingVals = sheet.getRange(2, colLoading + 1, rowCount, 1).getValues();
    var revisionVals = sheet.getRange(2, colRevision + 1, rowCount, 1).getValues();
    var readinessVals = sheet.getRange(2, colReadiness + 1, rowCount, 1).getValues();

    var today = new Date();
    today = new Date(today.getFullYear(), today.getMonth(), today.getDate());

    var flags = [];
    for (var i = 0; i < rowCount; i++) {
      var overdue = isOverdueRow_(
        loadingVals[i][0], revisionVals[i][0], readinessVals[i][0], today
      );
      flags.push([overdue ? "TRUE" : "FALSE"]);
    }
    sheet.getRange(2, helperColumn1Based, rowCount, 1).setValues(flags);
  }

  try {
    sheet.hideColumns(helperColumn1Based);
  } catch (err) {
    // Non-fatal — filtering still works correctly even if this column
    // stays visible (e.g. permissions issue hiding columns).
  }

  return helperColumn1Based - 1; // 0-based, for Sheets API filter criteria
}

/**
 * True when a row counts as "Over Due" — mirrors kpi_engine.py's
 * overdue_breakup mask exactly:
 *   not yet dispatched (Loading date blank/unparseable) AND
 *   overdue on production commitment, checked against the Revise Date if
 *   one's been given, falling back to the (original) Readiness Date when
 *   no revise date has been set yet.
 */
function isOverdueRow_(loadingValue, revisionValue, readinessValue, today) {
  return (
    parseSheetDate_(loadingValue) === null &&
    overdueEffectivePast_(revisionValue, readinessValue, today)
  );
}

/**
 * True when the "effective" commitment date is strictly before `today`.
 * The effective date is the revision date when it parses to a real date at
 * all (even a future one — an explicit revision always wins), otherwise the
 * readiness date. Matches kpi_engine.py's _blank_or_fallback_past.
 */
function overdueEffectivePast_(revisionValue, readinessValue, today) {
  var revision = parseSheetDate_(revisionValue);
  if (revision !== null) {
    return revision.getTime() < today.getTime();
  }
  var readiness = parseSheetDate_(readinessValue);
  return readiness !== null && readiness.getTime() < today.getTime();
}

/**
 * Parses a sheet date cell into a local-midnight Date, or null if the cell
 * is blank/unparseable. Handles both a real Date-typed cell (possible after
 * a manual edit in the UI) and the day-first "DD-MM-YYYY" text string that
 * app/clients/sheets_client.py's overwrite_worksheet writes for bulk loads.
 */
function parseSheetDate_(value) {
  if (value instanceof Date) {
    if (isNaN(value.getTime())) return null;
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  }
  var s = String(value || "").trim();
  if (!s) return null;
  var m = s.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);
  if (!m) return null;
  var day = parseInt(m[1], 10);
  var month = parseInt(m[2], 10);
  var year = parseInt(m[3], 10);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  var parsed = new Date(year, month - 1, day);
  // Reject e.g. 31-02-2026, which JS would otherwise silently roll into March.
  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null;
  }
  return parsed;
}

/**
 * One-off cleanup: run this manually from the Apps Script editor (select
 * "resetFilterViewCache" in the function dropdown, then Run) if country
 * links start opening to blank/stale filtered views — e.g. right after the
 * sheet's data was fully cleared and rewritten. Deletes every cached fvid
 * Script Property AND every Filter View this script created (title starts
 * with "Country: "), so the next click on each country builds a fresh view
 * against the current data instead of reusing a stale one.
 */
function resetFilterViewCache() {
  var props = PropertiesService.getScriptProperties();
  var keys = props.getKeys().filter(function (k) {
    return k.indexOf("fvid:") === 0;
  });
  keys.forEach(function (k) {
    props.deleteProperty(k);
  });

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(FILTER_TAB_NAME);
  var removed = 0;
  if (sheet) {
    // Filter Views live outside the base SpreadsheetApp service, so they're
    // only reachable (read or delete) via the Advanced Sheets API, same as
    // getOrCreateFilterView/listFilterViewIds above.
    var meta = Sheets.Spreadsheets.get(ss.getId(), {
      fields: "sheets(properties.sheetId,filterViews(filterViewId,title))"
    });
    var deleteRequests = [];
    (meta.sheets || []).forEach(function (s) {
      if (s.properties.sheetId !== sheet.getSheetId() || !s.filterViews) return;
      s.filterViews.forEach(function (fv) {
        if (String(fv.title || "").indexOf("Country: ") === 0) {
          deleteRequests.push({
            deleteFilterView: { filterId: fv.filterViewId }
          });
        }
      });
    });
    if (deleteRequests.length) {
      Sheets.Spreadsheets.batchUpdate({ requests: deleteRequests }, ss.getId());
      removed = deleteRequests.length;
    }
  }

  Logger.log(
    "Cleared " + keys.length + " cached fvid propert" + (keys.length === 1 ? "y" : "ies") +
    " and removed " + removed + " matching Filter View(s)."
  );
}

function listFilterViewIds(ss, sheetId) {
  var meta = Sheets.Spreadsheets.get(ss.getId(), {
    fields: "sheets(properties.sheetId,filterViews.filterViewId)"
  });
  var ids = {};
  (meta.sheets || []).forEach(function (s) {
    if (s.properties.sheetId === sheetId && s.filterViews) {
      s.filterViews.forEach(function (fv) {
        ids[String(fv.filterViewId)] = true;
      });
    }
  });
  return ids;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

/**
 * Index of `header` in `headers`, or -1 if absent. Normalizes the same way
 * as getHeaders() in code.gs (strips non-breaking spaces, trims, collapses
 * internal double spaces) so both scripts agree on what a header "is" even
 * when the sheet has stray/doubled whitespace (e.g. the real
 * "no of commitment loading  changes" header has a double space).
 */
function findColumnIndex_(headers, header) {
  for (var i = 0; i < headers.length; i++) {
    if (normalizeHeader_(headers[i]) === header) {
      return i;
    }
  }
  return -1;
}

function normalizeHeader_(value) {
  return String(value)
    .replace(/\u00A0/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

/**************************************************************
 * Manual test helpers.
 *
 * doGet(e) only receives a real `e` when Google calls it for an actual HTTP
 * request to the deployed /exec URL — clicking "Run" on doGet itself always
 * passes no arguments, which is exactly the TypeError this file used to
 * throw. To exercise doGet from the editor instead, select one of the
 * functions below in the function dropdown and click Run, then check
 * View > Logs (or Execution log) for the result.
 **************************************************************/

/** Happy path: fetches a real country from the sheet and filters on it. */
function test_doGet() {
  var country = getSampleCountry_();
  var result = doGet({ parameter: { country: country } });
  Logger.log("country=" + country + " ->\n" + result.getContent());
}

/** doGet called the way the editor's Run button calls it: no event at all. */
function test_doGet_noEvent() {
  var result = doGet();
  Logger.log(result.getContent());
}

/** Missing 'country' query param. */
function test_doGet_missingCountry() {
  var result = doGet({ parameter: {} });
  Logger.log(result.getContent());
}

/** A country with no matching rows — still builds a (empty) filter view. */
function test_doGet_unknownCountry() {
  var result = doGet({ parameter: { country: "Nowhereland" } });
  Logger.log(result.getContent());
}

/** Wrong FILTER_TAB_NAME — exercises the "Tab not found" branch. */
function test_doGet_missingTab() {
  var realTab = FILTER_TAB_NAME;
  FILTER_TAB_NAME = "____does_not_exist____";
  try {
    var result = doGet({ parameter: { country: "USA" } });
    Logger.log(result.getContent());
  } finally {
    FILTER_TAB_NAME = realTab;
  }
}

/**
 * Cross-check helper: logs the overdue MACHINE count (sum of Quantity, same
 * as kpi_engine.py's `machines()` helper — not a row count) per country
 * exactly as refreshOverdueHelperColumn_/isOverdueRow_ compute it, so it can
 * be diffed against the "Over Due Breakup" numbers in the emailed report
 * (compute_country_breakup in app/core/kpi_engine.py). A mismatch here means
 * the two overdue rules have drifted apart again.
 */
function test_overdueCountsByCountry() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(FILTER_TAB_NAME);
  if (!sheet) {
    throw new Error("Tab '" + FILTER_TAB_NAME + "' not found.");
  }

  refreshOverdueHelperColumn_(sheet);

  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var colCountry = findColumnIndex_(headers, FILTER_COLUMN_HEADER);
  var colQuantity = findColumnIndex_(headers, "Quantity");
  var colHelper = findColumnIndex_(headers, OVERDUE_HELPER_HEADER);
  var lastRow = sheet.getLastRow();
  if (colCountry === -1 || colQuantity === -1 || lastRow < 2) {
    Logger.log("No data to summarize (missing Country/Quantity column, or no rows).");
    return;
  }

  var countryVals = sheet.getRange(2, colCountry + 1, lastRow - 1, 1).getValues();
  var quantityVals = sheet.getRange(2, colQuantity + 1, lastRow - 1, 1).getValues();
  var helperVals = sheet.getRange(2, colHelper + 1, lastRow - 1, 1).getValues();

  var totals = {};
  for (var i = 0; i < countryVals.length; i++) {
    var country = String(countryVals[i][0]).trim();
    if (!country) continue;
    if (helperVals[i][0] === "TRUE") {
      var qty = Number(quantityVals[i][0]) || 0;
      totals[country] = (totals[country] || 0) + qty;
    }
  }

  Object.keys(totals)
    .sort()
    .forEach(function (country) {
      Logger.log(country + ": " + totals[country]);
    });
}

/** First non-blank Country value in the sheet, for tests to filter on. */
function getSampleCountry_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(FILTER_TAB_NAME);
  if (!sheet) {
    throw new Error("Tab '" + FILTER_TAB_NAME + "' not found.");
  }
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var colIndex = findColumnIndex_(headers, FILTER_COLUMN_HEADER);
  if (colIndex === -1) {
    throw new Error(
      "Column '" + FILTER_COLUMN_HEADER + "' not found in " + FILTER_TAB_NAME
    );
  }
  var values = sheet
    .getRange(2, colIndex + 1, Math.max(sheet.getLastRow() - 1, 0), 1)
    .getValues();
  for (var i = 0; i < values.length; i++) {
    var country = String(values[i][0]).trim();
    if (country) return country;
  }
  throw new Error("No non-blank '" + FILTER_COLUMN_HEADER + "' value found to test with.");
}
