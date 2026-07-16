function onEdit(e) {
  if (!e || !e.range) return;

  const sheet = e.range.getSheet();
  const row = e.range.getRow();
  const col = e.range.getColumn();

  if (row === 1) return;

  // 1. Production Commitment Revise Date edited (J)
  if (col === 10) {
    const countCell = sheet.getRange(row, 11); // K
    let current = Number(countCell.getValue()) || 0;
    countCell.setValue(current + 1);
  }

  // 2. Container Revision Date edited (O)
  if (col === 15) {
    const countCell = sheet.getRange(row, 16); // P
    let current = Number(countCell.getValue()) || 0;
    countCell.setValue(current + 1);
  }

  // 3. Backlog Days = Production Completion - Production Commitment Date
  const readiness = sheet.getRange(row, 9).getValue();    // I
  const completion = sheet.getRange(row, 12).getValue();  // L
  const backlogCell = sheet.getRange(row, 13);            // M

  if (isDate(readiness) && isDate(completion)) {
    backlogCell.setValue(daysBetween(readiness, completion));
  } else {
    backlogCell.clearContent();
  }

  // 4. Overdue Days = Loading - Container Placement
  const placement = sheet.getRange(row, 14).getValue();   // N
  const loading = sheet.getRange(row, 17).getValue();     // Q
  const overdueCell = sheet.getRange(row, 18);            // R

  if (isDate(placement) && isDate(loading)) {
    overdueCell.setValue(daysBetween(placement, loading));
  } else {
    overdueCell.clearContent();
  }
}

function isDate(value) {
  return value instanceof Date && !isNaN(value);
}

function daysBetween(startDate, endDate) {
  return Math.round(
    (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)
  );
}
