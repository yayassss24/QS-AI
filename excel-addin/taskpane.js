/**
 * QS BOQ AI — Excel Add-in Taskpane
 *
 * BACKEND_URL dapat dikonfigurasi via:
 * 1. Query parameter ?backend=http://localhost:8000
 * 2. Fallback ke window.location.origin (jika diserve dari backend)
 * 3. Default http://localhost:8000
 */

var BACKEND_URL = (function() {
  var params = new URLSearchParams(window.location.search);
  var fromQuery = params.get("backend");
  if (fromQuery) return fromQuery;
  if (window.location.origin && window.location.origin !== "null") {
    return window.location.origin;
  }
  return "http://localhost:8000";
})();

var currentDimensions = null;

Office.onReady(function (info) {
  if (info.host === Office.HostType.Excel) {
    document.getElementById("status").textContent = "Siap. Backend: " + BACKEND_URL;
  }
});

function setStatus(msg, type) {
  var el = document.getElementById("status");
  el.textContent = msg;
  el.className = "status " + (type || "");
}

// === EXTRACT DIMENSIONS ===
async function processFile() {
  var fileInput = document.getElementById("fileInput");
  var file = fileInput.files[0];
  if (!file) {
    setStatus("Pilih file terlebih dahulu", "error");
    return;
  }

  setStatus("Memproses...", "info");

  var formData = new FormData();
  formData.append("file", file);

  try {
    var resp = await fetch(BACKEND_URL + "/api/extract-file", {
      method: "POST",
      body: formData,
    });
    var data = await resp.json();

    if (data.status === "ok") {
      currentDimensions = data.data;
      var total = data.data && data.data.items ? data.data.items.length : 0;
      setStatus("Berhasil: " + total + " item", "ok");
    } else {
      setStatus("Error: " + (data.message || "Unknown error"), "error");
    }
  } catch (err) {
    setStatus("Gagal: " + err.message, "error");
  }
}

// === READ HEADERS FROM ACTIVE SHEET ===
async function getSheetHeaders() {
  return new Promise(function (resolve, reject) {
    Excel.run(function (context) {
      var sheet = context.workbook.worksheets.getActiveWorksheet();
      var range = sheet.getRange("1:3");
      range.load("values");
      return context.sync().then(function () {
        var headers = [];
        var row1 = range.values[0] || [];
        for (var col = 0; col < row1.length; col++) {
          if (row1[col] !== null && row1[col] !== undefined && String(row1[col]).trim() !== "") {
            headers.push(String(row1[col]).trim());
          }
        }
        if (headers.length === 0) {
          var row2 = range.values[1] || [];
          for (var col = 0; col < row2.length; col++) {
            if (row2[col] !== null && row2[col] !== undefined && String(row2[col]).trim() !== "") {
              headers.push(String(row2[col]).trim());
            }
          }
        }
        resolve(headers);
      });
    }).catch(function (err) {
      reject(err);
    });
  });
}

// === GENERATE BOQ ===
async function generateBoq() {
  if (!currentDimensions) {
    setStatus("Ekstrak dimensi dulu", "error");
    return;
  }

  setStatus("Mendeteksi template...", "info");

  try {
    var headers = await getSheetHeaders();
    if (headers.length === 0) {
      setStatus("Tidak bisa membaca header sheet. Isi header di baris 1-3.", "error");
      return;
    }

    setStatus("Menghitung BOQ...", "info");

    var items = currentDimensions.items || (Array.isArray(currentDimensions) ? currentDimensions : []);
    var resp = await fetch(BACKEND_URL + "/api/compute-boq-from-json", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dimensions: { items: items },
        headers: headers,
      }),
    });
    var data = await resp.json();

    if (data.status !== "ok") {
      setStatus("Error: " + (data.message || "Gagal"), "error");
      return;
    }

    setStatus("Menulis ke Excel...", "info");
    await writeBoqToSheet(data.data);

  } catch (err) {
    setStatus("Gagal: " + err.message, "error");
  }
}

// === COLUMN LETTER TO INDEX ===
function colLetterToIndex(letters) {
  var index = 0;
  for (var i = 0; i < letters.length; i++) {
    index = index * 26 + (letters.charCodeAt(i) - 64);
  }
  return index - 1; // zero-based
}

// === WRITE BOQ TO SHEET ===
async function writeBoqToSheet(boqData) {
  var items = boqData.items || [];

  await Excel.run(async function (context) {
    var sheet = context.workbook.worksheets.getActiveWorksheet();

    for (var i = 0; i < items.length; i++) {
      var item = items[i];

      Object.entries(item.cells || {}).forEach(function (_a) {
        var cellAddr = _a[0];
        var cellInfo = _a[1];

        var match = cellAddr.match(/([A-Z]+)(\d+)/);
        if (!match) return;
        var colLetter = match[1];
        var rowNum = parseInt(match[2], 10);
        var colIndex = colLetterToIndex(colLetter);

        var cell = sheet.getCell(rowNum - 1, colIndex);

        if (cellInfo.type === "formula") {
          cell.formulas = [[cellInfo.value]];
        } else if (cellInfo.value !== null && cellInfo.value !== undefined) {
          cell.values = [[cellInfo.value]];
        }
        if (cellInfo.color) {
          cell.format.fill.color = cellInfo.color;
        }
      });

      Object.entries(item.comments || {}).forEach(function (_a) {
        var cellAddr = _a[0];
        var comment = _a[1];

        var match = cellAddr.match(/([A-Z]+)(\d+)/);
        if (!match) return;
        var colLetter = match[1];
        var rowNum = parseInt(match[2], 10);
        var colIndex = colLetterToIndex(colLetter);

        var cell = sheet.getCell(rowNum - 1, colIndex);
        try {
          var c = sheet.comments.add(cell);
          c.text = comment;
        } catch (e) {
          // comment mungkin sudah ada
        }
        if (comment.includes("⚠️")) {
          cell.format.fill.color = "#FAEEDA";
        }
      });
    }

    await context.sync();
    setStatus("BOQ berhasil ditulis (" + items.length + " item)", "ok");
  }).catch(function (err) {
    setStatus("Error: " + err.message, "error");
  });
}
