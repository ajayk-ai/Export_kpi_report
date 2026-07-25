/**************************************************************
 * SCM AUTO CALCULATION
 * Uses Header Names instead of Column Numbers
 * (Robust to header reordering, renaming spacing, and paste edits)
 *
 * Header names below must stay in lockstep with the SCM_Export_Orders
 * schema used by make_test_data.py and app/core/kpi_engine.py's COL_*
 * constants (production commitment Date / production commitment Revise
 * Date, etc.) - if those change, update REQUIRED_HEADERS here too.
 **************************************************************/

const REQUIRED_HEADERS = [
  "production commitment Revise Date",
  "no of times commitment changes(prod)",
  "Container Revision Date",
  "no of comm container changes",
  "revision commitment of loading date",
  "no of commitment loading changes",
  "production commitment Date",
  "Production Completion (Roll-out)Date",
  "backlog days",
  "Container Placement date",
  "Loading (Dispatched) Date",
  "over due days"
];

function onEdit(e) {
  if (!e || !e.range) return;
  const sheet = e.range.getSheet();
  const H = getHeaders(sheet);

  // Validate headers exist before doing anything - surface problems loudly
  const missing = REQUIRED_HEADERS.filter(function(h) { return !H[h]; });
  if (missing.length > 0) {
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "SCM script: missing/renamed headers -> " + missing.join(", "),
      "Header mismatch",
      10
    );
    Logger.log("Missing headers: " + missing.join(", "));
    return;
  }

  // Handle full edited range (covers paste of multiple rows/cols, not just single cell)
  const startRow = e.range.getRow();
  const numRows = e.range.getNumRows();
  const editedCol = e.range.getColumn(); // used only for the "increment" checks below

  for (let r = startRow; r < startRow + numRows; r++) {
    if (r == 1) continue; // skip header row
    calculateRow(sheet, r, editedCol, H);
  }
}

/**************************************************************
 * Calculate One Row
 **************************************************************/
function calculateRow(sheet, row, editedCol, H) {
  try {

    //----------------------------------------------------------
    // Machine Revision Count
    //----------------------------------------------------------
    if (editedCol == H["production commitment Revise Date"]) {
      const cell = sheet.getRange(
        row,
        H["no of times commitment changes(prod)"]
      );
      cell.setNumberFormat("0");
      cell.setValue((Number(cell.getValue()) || 0) + 1);
    }

    //----------------------------------------------------------
    // Container Revision Count
    //----------------------------------------------------------
    if (editedCol == H["Container Revision Date"]) {
      const cell = sheet.getRange(
        row,
        H["no of comm container changes"]
      );
      cell.setNumberFormat("0");
      cell.setValue((Number(cell.getValue()) || 0) + 1);
    }

    //----------------------------------------------------------
    // Commitment Loading Revision Count
    //----------------------------------------------------------
    if (editedCol == H["revision commitment of loading date"]) {
      const cell = sheet.getRange(
        row,
        H["no of commitment loading changes"]
      );
      cell.setNumberFormat("0");
      cell.setValue((Number(cell.getValue()) || 0) + 1);
    }

    //----------------------------------------------------------
    // Backlog Days
    //----------------------------------------------------------
    let readiness = sheet.getRange(row, H["production commitment Date"]).getValue();
    let completion = sheet.getRange(row, H["Production Completion (Roll-out)Date"]).getValue();

    readiness = convertToDate(readiness);
    completion = convertToDate(completion);

    const backlogCell = sheet.getRange(row, H["backlog days"]);
    if (readiness && completion) {
      const diff = Math.floor(
        (completion.getTime() - readiness.getTime()) / 86400000
      );
      backlogCell.setNumberFormat("0");
      backlogCell.setValue(diff);
    } else {
      backlogCell.clearContent();
    }

    //----------------------------------------------------------
    // Over Due Days
    //----------------------------------------------------------
    let placement = sheet.getRange(row, H["Container Placement date"]).getValue();
    let loading = sheet.getRange(row, H["Loading (Dispatched) Date"]).getValue();

    placement = convertToDate(placement);
    loading = convertToDate(loading);

    const overdueCell = sheet.getRange(row, H["over due days"]);
    if (placement && loading) {
      const diff = Math.floor(
        (loading.getTime() - placement.getTime()) / 86400000
      );
      overdueCell.setNumberFormat("0");
      overdueCell.setValue(diff);
    } else {
      overdueCell.clearContent();
    }

  } catch (err) {
    // Surface errors instead of only logging them silently
    SpreadsheetApp.getActiveSpreadsheet().toast(
      "Row " + row + " calc error: " + err.message,
      "SCM script error",
      10
    );
    Logger.log("Row " + row + " error: " + err);
  }
}

/**************************************************************
 * Read Header Row (robust: trims + collapses whitespace,
 * strips non-breaking spaces, but keeps exact case so headers
 * with different casing show up as "missing" rather than
 * silently merging two different columns)
 **************************************************************/
function getHeaders(sheet) {
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn())
    .getValues()[0];
  const H = {};
  headers.forEach(function(h, i) {
    const clean = String(h)
      .replace(/\u00A0/g, " ") // non-breaking space -> normal space
      .trim()
      .replace(/\s+/g, " ");   // collapse internal double spaces
    if (clean) H[clean] = i + 1;
  });
  return H;
}

/**************************************************************
 * Convert Any Value To Date
 **************************************************************/
function convertToDate(value) {
  if (value === "" || value == null) return null;
  if (value instanceof Date) return value;

  if (typeof value == "number") {
    return new Date(
      Math.round((value - 25569) * 86400 * 1000)
    );
  }

  if (typeof value == "string") {
    value = value.trim();
    value = value.replace(/\./g, "/");
    value = value.replace(/-/g, "/");

    let d = new Date(value);
    if (!isNaN(d)) return d;

    const p = value.split("/");
    if (p.length == 3) {
      const day = Number(p[0]);
      const month = Number(p[1]) - 1;
      const year = Number(p[2]);
      d = new Date(year, month, day);
      if (!isNaN(d)) return d;
    }
  }

  return null;
}

/**************************************************************
 * Recalculate Entire Sheet
 * (Use this to fix rows where onEdit never fired - e.g. bulk
 * pasted / imported data, or rows entered before this fix)
 *
 * NOTE: Recalculating all rows will NOT re-trigger the
 * increment counters (no of comm container changes, no of
 * commitment loading, no of times commitment changes(prod))
 * since editedCol is passed as -1 here. Those counters only
 * increment on live onEdit events, by design, so bulk pastes
 * / recalculation don't inflate the change counts.
 **************************************************************/
function recalculateAllRows() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const H = getHeaders(sheet);

  const missing = REQUIRED_HEADERS.filter(function(h) { return !H[h]; });
  if (missing.length > 0) {
    SpreadsheetApp.getUi().alert(
      "Cannot recalculate - missing/renamed headers:\n" + missing.join("\n")
    );
    return;
  }

  const lastRow = sheet.getLastRow();
  for (let row = 2; row <= lastRow; row++) {
    calculateRow(sheet, row, -1, H);
  }

  SpreadsheetApp.getActiveSpreadsheet().toast("Recalculated all rows.", "Done", 5);
}

/**************************************************************
 * Debug Headers
 **************************************************************/
function printHeaders() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const H = getHeaders(sheet);
  Logger.log(JSON.stringify(H, null, 2));

  const missing = REQUIRED_HEADERS.filter(function(h) { return !H[h]; });
  if (missing.length > 0) {
    Logger.log("MISSING: " + missing.join(", "));
  } else {
    Logger.log("All required headers found.");
  }
}

/**************************************************************
 * Menu for manual recalculation
 **************************************************************/
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("SCM Tools")
    .addItem("Recalculate All Rows", "recalculateAllRows")
    .addItem("Check Headers", "printHeaders")
    .addToUi();
}
