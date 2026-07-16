/**************************************************************
 * Country Filter Link
 *
 * Lets the KPI email's "Over Due Breakup" numbers deep-link into
 * this spreadsheet, pre-filtered to that one country, without
 * disturbing what any other viewer currently has filtered (each
 * click gets its own Filter View instead of touching the shared
 * Basic Filter).
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
 * Returns the filterViewId for `country` on `sheet`. Reuses the view from
 * a previous click (id cached in Script Properties) as long as it still
 * exists; otherwise creates a fresh one via the Sheets Advanced Service.
 */
function getOrCreateFilterView(ss, sheet, country) {
  var props = PropertiesService.getScriptProperties();
  var key = "fvid:" + sheet.getSheetId() + ":" + country;
  var cached = props.getProperty(key);
  var existingIds = listFilterViewIds(ss, sheet.getSheetId());

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
              endColumnIndex: headers.length
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

/** Index of `header` in `headers` (whitespace-trimmed), or -1 if absent. */
function findColumnIndex_(headers, header) {
  for (var i = 0; i < headers.length; i++) {
    if (String(headers[i]).trim() === header) {
      return i;
    }
  }
  return -1;
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
