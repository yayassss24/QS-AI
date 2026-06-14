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

async function writeToSheet() {
  if (!currentDimensions) {
    setStatus("Ekstrak dimensi dulu", "error");
    return;
  }

  setStatus("Menulis ke Excel...", "info");

  try {
    await Excel.run(async function (context) {
      var sheet = context.workbook.worksheets.getActiveWorksheet();

      var items = currentDimensions.items || [];
      var row = 1;

      for (var i = 0; i < items.length; i++) {
        var item = items[i];
        var pCell = sheet.getCell(row, 2);
        var lCell = sheet.getCell(row, 3);
        var tCell = sheet.getCell(row, 4);
        var volCell = sheet.getCell(row, 5);

        if (item.P != null) {
          pCell.values = [[item.P]];
          pCell.format.fill.color = "#EEEDFE";
        }
        if (item.L != null) {
          lCell.values = [[item.L]];
          lCell.format.fill.color = "#EEEDFE";
        }
        if (item.T != null) {
          tCell.values = [[item.T]];
          tCell.format.fill.color = "#EEEDFE";
        }

        if (item.P != null && item.L != null && item.T != null) {
          volCell.formulas = [["=B" + (row + 1) + "*C" + (row + 1) + "*D" + (row + 1)]];
        }

        if (item.confidence < 0.7) {
          pCell.format.fill.color = "#FAEEDA";
          lCell.format.fill.color = "#FAEEDA";
          tCell.format.fill.color = "#FAEEDA";
          var comment = sheet.comments.add(pCell);
          comment.text = "Perlu verifikasi manual";
        }

        row++;
      }

      await context.sync();
      setStatus("BOQ berhasil ditulis", "ok");
    });
  } catch (err) {
    setStatus("Error: " + err.message, "error");
  }
}
