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
  var country = ((e.parameter && e.parameter.country) || "").trim();
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
  var colIndex = -1;
  for (var i = 0; i < headers.length; i++) {
    if (String(headers[i]).trim() === FILTER_COLUMN_HEADER) {
      colIndex = i;
      break;
    }
  }
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
