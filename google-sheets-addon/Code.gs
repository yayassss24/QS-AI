/**
 * QS BOQ AI Extension — Google Sheets Add-on
 *
 * Menu, sidebar, sheet write, backend communication
 */

let BACKEND_URL = PropertiesService.getScriptProperties().getProperty("BACKEND_URL") || "https://irresolutely-vibronic-bulah.ngrok-free.dev";

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("QS BOQ AI")
    .addItem("Buka Panel", "showSidebar")
    .addItem("Generate BOQ dari Sheet", "generateBoqFromSheet")
    .addSeparator()
    .addItem("Set Backend URL", "showSettings")
    .addToUi();
}

function showSettings() {
  const ui = SpreadsheetApp.getUi();
  const result = ui.prompt(
    "Backend URL",
    "Masukkan URL backend server:",
    ui.ButtonSet.OK_CANCEL
  );
  if (result.getSelectedButton() === ui.Button.OK) {
    BACKEND_URL = result.getResponseText().replace(/\/+$/, "");
    PropertiesService.getScriptProperties().setProperty("BACKEND_URL", BACKEND_URL);
    ui.alert("Backend URL disimpan: " + BACKEND_URL);
  }
}

function showSidebar() {
  const html = HtmlService.createHtmlOutputFromFile("Sidebar")
    .setTitle("QS BOQ AI")
    .setWidth(300);
  SpreadsheetApp.getUi().showSidebar(html);
}

// === USER ID ===
function getUserSessionId() {
  const props = PropertiesService.getUserProperties();
  let userId = props.getProperty("qs_boq_user_id");
  if (!userId) {
    userId = "gas_" + Utilities.getUuid();
    props.setProperty("qs_boq_user_id", userId);
  }
  return userId;
}

// === BACKEND JSON CALLS ===
function callBackend(endpoint, payload) {
  const response = UrlFetchApp.fetch(BACKEND_URL + endpoint, {
    method: "POST",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });
  return response.getContentText();
}

// === FILE UPLOAD (base64 → multipart) ===
function processFileUpload(base64Data, filename, mimeType, scale) {
  const decoded = Utilities.base64Decode(base64Data);
  const blob = Utilities.newBlob(decoded, "application/octet-stream", filename);
  const userId = getUserSessionId();

  const payload = { file: blob, user_id: userId };
  if (scale) payload.scale = scale;

  const response = UrlFetchApp.fetch(BACKEND_URL + "/api/extract-file", {
    method: "POST",
    payload: payload,
    muteHttpExceptions: true,
  });
  return response.getContentText();
}

// === GENERATE BOQ (kirim headers + dimensions via JSON) ===
function generateBoq(dimensionsJson) {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastCol = sheet.getLastColumn();

  let headers = [];
  let columnMap = {};
  if (lastCol > 0) {
    const values = sheet.getRange(1, 1, 3, lastCol).getValues();
    for (let row = 0; row < 3; row++) {
      headers = [];
      columnMap = {};
      for (let col = 0; col < lastCol; col++) {
        const val = values[row][col];
        if (val && String(val).trim()) {
          const key = String(val).trim();
          headers.push(key);
          columnMap[key] = col + 1;
        }
      }
      if (headers.length > 0) break;
    }
  }

  if (headers.length === 0) {
    headers = ["Uraian Pekerjaan", "P", "L", "T", "Satuan", "Volume"];
  }

  const userId = getUserSessionId();
  const response = UrlFetchApp.fetch(BACKEND_URL + "/api/compute-boq-from-json", {
    method: "POST",
    contentType: "application/json",
    payload: JSON.stringify({
      dimensions: JSON.parse(dimensionsJson),
      headers: headers,
      column_map: Object.keys(columnMap).length > 0 ? columnMap : undefined,
    }),
    muteHttpExceptions: true,
  });
  return response.getContentText();
}

// === CHAT ===
function sendChatMessage(message) {
  const userId = getUserSessionId();
  return callBackend("/api/chat", {
    user_message: message,
    user_id: userId,
    boq_state: [],
    template_mapping: {},
    file_names: {},
  });
}

// === BYOK ===
function saveByok(apiKey) {
  const userId = getUserSessionId();
  return callBackend("/api/byok/save", { user_id: userId, api_key: apiKey });
}

function clearByok() {
  const userId = getUserSessionId();
  return callBackend("/api/byok/delete", { user_id: userId });
}

// === GENERATE BOQ FROM SHEET DATA (tanpa upload file) ===
function generateBoqFromSheet() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastCol = sheet.getLastColumn();
  if (lastCol < 1) {
    SpreadsheetApp.getUi().alert("Tidak ada data di sheet.");
    return;
  }

  const range = sheet.getRange(1, 1, 3, lastCol);
  const values = range.getValues();
  let headers = [];

  for (let row = 0; row < 3; row++) {
    headers = [];
    for (let col = 0; col < lastCol; col++) {
      const val = values[row][col];
      if (val && String(val).trim()) {
        headers.push(String(val).trim());
      }
    }
    if (headers.length > 0) break;
  }

  if (headers.length === 0) {
    SpreadsheetApp.getUi().alert("Tidak ada header di baris 1-3.");
    return;
  }

  const lastRow = sheet.getLastRow();
  const dataRange = sheet.getRange(4, 1, Math.max(0, lastRow - 3), headers.length);
  const dataValues = dataRange.getValues();

  const items = [];
  for (let i = 0; i < dataValues.length; i++) {
    const cells = {};
    let hasData = false;
    for (let col = 0; col < headers.length; col++) {
      const val = dataValues[i][col];
      if (val !== "" && val !== null && val !== undefined) {
        cells[headers[col]] = String(val);
        hasData = true;
      }
    }
    if (hasData) items.push({ cells });
  }

  const payload = { dimensions: { items }, headers };
  const response = UrlFetchApp.fetch(BACKEND_URL + "/api/compute-boq-from-json", {
    method: "POST",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
    timeout: 120000,
  });

  const result = JSON.parse(response.getContentText());
  if (result.status !== "ok") {
    SpreadsheetApp.getUi().alert("Error: " + (result.message || "Gagal menghitung BOQ"));
    return;
  }

  writeBoqFormulaData(JSON.stringify(result.data.items));
  SpreadsheetApp.getUi().alert("BOQ berhasil ditulis ke sheet!");
}

// === WRITE FORMULA DATA TO SHEET ===
function writeBoqFormulaData(boqDataJson) {
  const sheet = SpreadsheetApp.getActiveSheet();
  const items = JSON.parse(boqDataJson);

  items.forEach(function (item) {
    Object.entries(item.cells || {}).forEach(function ([cellAddr, cellInfo]) {
      const cell = sheet.getRange(cellAddr);
      if (cellInfo.type === "formula") {
        cell.setFormula(cellInfo.value);
      } else if (cellInfo.value !== null && cellInfo.value !== undefined) {
        cell.setValue(cellInfo.value);
      }
      if (cellInfo.color) {
        cell.setBackground(cellInfo.color);
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

  return JSON.stringify({ status: "ok", total: items.length });
}
