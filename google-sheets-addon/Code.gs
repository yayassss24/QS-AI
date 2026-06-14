/**
 * QS BOQ AI Extension — Google Sheets Add-on
 * 
 * Menu, sidebar, writeBoqToSheet, callBackend
 */

const BACKEND_URL = "https://your-backend.railway.app";

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("QS Assistant")
    .addItem("Buka Panel", "showSidebar")
    .addToUi();
}

function showSidebar() {
  const html = HtmlService.createHtmlOutputFromFile("Sidebar")
    .setTitle("QS BOQ AI")
    .setWidth(300);
  SpreadsheetApp.getUi().showSidebar(html);
}

function detectTemplate() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getActiveSheet();
  const headers = sheet.getRange(1, 1, 3, sheet.getLastColumn()).getValues();
  return JSON.stringify(headers);
}

function getSupportedFormats() {
  return JSON.stringify({
    image: [".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif", ".bmp", ".heic", ".heif"],
    pdf: [".pdf"],
    cad: [".dxf"],
    all_accept: ".pdf,.jpg,.jpeg,.png,.webp,.tiff,.tif,.bmp,.heic,.heif,.dxf",
  });
}

function writeBoqToSheet(boqData) {
  /**
   * Terima JSON boqData dari backend dan tulis ke sheet aktif.
   * boqData: [{row, cells: {C7: {value, type, color}}, comments: {...}}]
   */
  const sheet = SpreadsheetApp.getActiveSheet();
  const data = JSON.parse(boqData);

  data.forEach(function (item) {
    Object.entries(item.cells).forEach(function ([cellAddr, cellInfo]) {
      const cell = sheet.getRange(cellAddr);

      if (cellInfo.type === "formula") {
        cell.setFormula(cellInfo.value);
      } else if (cellInfo.type === "dimension") {
        cell.setValue(cellInfo.value);
        cell.setBackground("#EEEDFE");
      } else if (cellInfo.type === "angka") {
        cell.setValue(cellInfo.value);
      }
    });

    Object.entries(item.comments || {}).forEach(function ([cellAddr, comment]) {
      const cell = sheet.getRange(cellAddr);
      const note = cell.getNote();
      cell.setNote(note ? note + "\n" + comment : comment);
      if (comment.includes("⚠️")) {
        cell.setBackground("#FAEEDA");
      }
    });
  });

  return JSON.stringify({ status: "ok" });
}

function callBackend(endpoint, payload) {
  const response = UrlFetchApp.fetch(BACKEND_URL + endpoint, {
    method: "POST",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });
  return JSON.parse(response.getContentText());
}
