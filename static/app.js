const fileInput = document.getElementById("files");
const fileList = document.getElementById("file-list");
const form = document.getElementById("ocr-form");
const submitBtn = document.getElementById("submit-btn");
const clearBtn = document.getElementById("clear-btn");
const downloadOcrTxtBtn = document.getElementById("download-ocr-txt-btn");
const runSummaryBtn = document.getElementById("run-summary-btn");
const downloadOcrXlsxBtn = document.getElementById("download-ocr-xlsx-btn");
const downloadSummaryTxtBtn = document.getElementById("download-summary-txt-btn");
const downloadSummaryXlsxBtn = document.getElementById("download-summary-xlsx-btn");
const importTypeSelect = document.getElementById("import-type");
const statusEl = document.getElementById("status");
const statusDotEl = document.querySelector(".status-indicator-dot");
const resultsEl = document.getElementById("results");
const summaryResultsEl = document.getElementById("summary-results");
const resultMetaEl = document.getElementById("result-meta");
const summaryMetaEl = document.getElementById("summary-meta");
const layoutPreserveCheckbox = document.getElementById("layout-preserve");
const dropzoneLabel = document.getElementById("dropzone-label");

let previewUrls = [];
let lastOcrText = "";
let lastOcrPayload = null;
let lastSummaryPayload = null;
let lastSummaryText = "";
let lastDownloadOcrTxtName = "ocr-goc.txt";
let lastDownloadOcrXlsxName = "ocr-goc.xlsx";
let lastDownloadSummaryTxtName = "tom-tat-ai.txt";
let lastDownloadSummaryXlsxName = "tom-tat-ai.xlsx";

function getImportTypeLabel(value) {
  if (value === "complex_llm") {
    return "Phức tạp + Tối ưu hóa AI (Chậm)";
  }
  return "Rõ ràng (nhanh)";
}

function getOcrRunStatusMessage(value) {
  if (value === "complex_llm") {
    return "Đang trích xuất chế độ phức tạp + AI... vui lòng chờ.";
  }
  return "Đang trích xuất chế độ nhanh... vui lòng chờ.";
}

function setStatus(text, type = "idle") {
  if (statusEl) {
    statusEl.textContent = text;
  }
  if (statusDotEl) {
    statusDotEl.className = "status-indicator-dot";
    if (type === "active") {
      statusDotEl.classList.add("active");
    } else if (type === "running") {
      statusDotEl.classList.add("running");
    }
  }
}

function humanSize(bytes) {
  if (!Number.isFinite(bytes)) {
    return "";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB"];
  let size = bytes / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

function clearPreviews() {
  previewUrls.forEach((url) => URL.revokeObjectURL(url));
  previewUrls = [];
  fileList.innerHTML = "";
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function filenameFromContentDisposition(disposition) {
  if (!disposition) {
    return "";
  }

  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const asciiMatch = disposition.match(/filename="?([^"]+)"?/i);
  return asciiMatch?.[1] || "";
}

function clearSummaryPreview() {
  lastSummaryPayload = null;
  lastSummaryText = "";
  if (summaryResultsEl) {
    summaryResultsEl.className = "summary-results empty";
    summaryResultsEl.innerHTML = `
      <div class="empty-state-content">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="empty-icon"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <p>Chạy xong OCR, sau đó bấm nút "Chạy tóm tắt AI" để trích xuất bảng phân tích nội dung.</p>
      </div>
    `;
  }
  if (summaryMetaEl) {
    summaryMetaEl.textContent = "Chưa có tóm tắt.";
  }
}

function updateActionState() {
  const hasOcr = Boolean(lastOcrPayload);
  const hasSummary = Boolean(lastSummaryPayload);
  if (runSummaryBtn) {
    runSummaryBtn.disabled = !hasOcr;
  }
  if (downloadOcrTxtBtn) {
    downloadOcrTxtBtn.disabled = !hasOcr;
  }
  if (downloadOcrXlsxBtn) {
    downloadOcrXlsxBtn.disabled = !hasOcr;
  }
  if (downloadSummaryTxtBtn) {
    downloadSummaryTxtBtn.disabled = !hasSummary;
  }
  if (downloadSummaryXlsxBtn) {
    downloadSummaryXlsxBtn.disabled = !hasSummary;
  }
}

function buildSummaryText(payload) {
  const summaries = Array.isArray(payload?.summaries) ? payload.summaries : [];
  const lines = [];

  summaries.forEach((summaryFile, index) => {
    const filename = summaryFile.filename || `file-${index + 1}`;
    lines.push(`File: ${filename}`);
    if (summaryFile.detail) {
      lines.push(`Ghi chú: ${summaryFile.detail}`);
    }

    const rows = Array.isArray(summaryFile.rows) ? summaryFile.rows : [];
    rows.forEach((row, rowIndex) => {
      if (!row || typeof row !== "object") {
        return;
      }
      const group = row["Nhóm nội dung"] || "";
      const content = row["Nội dung chính"] || "";
      lines.push(`${rowIndex + 1}. ${group}: ${content}`.trim());
    });
    lines.push("");
  });

  return lines.join("\n").trim();
}

function renderSummaryResults(payload) {
  if (!summaryResultsEl) {
    return;
  }

  summaryResultsEl.classList.remove("empty");
  summaryResultsEl.innerHTML = "";

  const summaries = Array.isArray(payload?.summaries) ? payload.summaries : [];
  if (!summaries.length) {
    summaryResultsEl.classList.add("empty");
    summaryResultsEl.innerHTML = `
      <div class="empty-state-content">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="empty-icon"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <p>Không có dữ liệu tóm tắt nào được trích xuất.</p>
      </div>
    `;
    if (summaryMetaEl) {
      summaryMetaEl.textContent = "0 file.";
    }
    lastSummaryPayload = null;
    updateActionState();
    return;
  }

  let renderedAny = false;
  summaries.forEach((summaryFile) => {
    const item = document.createElement("article");
    item.className = "summary-item";

    const head = document.createElement("div");
    head.className = "summary-item-head";

    const title = document.createElement("strong");
    title.textContent = summaryFile.filename || "untitled";

    const meta = document.createElement("span");
    meta.textContent = summaryFile.detail || summaryFile.status || "";

    head.append(title, meta);
    item.appendChild(head);

    const rows = Array.isArray(summaryFile.rows) ? summaryFile.rows : [];
    if (!rows.length) {
      const empty = document.createElement("div");
      empty.className = "summary-empty";
      empty.textContent = "Không có dòng tóm tắt.";
      item.appendChild(empty);
    } else {
      const tableWrapper = document.createElement("div");
      tableWrapper.className = "summary-table-wrapper";

      const table = document.createElement("table");
      table.className = "summary-table";

      const thead = document.createElement("thead");
      const headRow = document.createElement("tr");
      ["Nhóm nội dung", "Nội dung chính"].forEach((label) => {
        const th = document.createElement("th");
        th.textContent = label;
        headRow.appendChild(th);
      });
      thead.appendChild(headRow);

      const tbody = document.createElement("tbody");
      rows.forEach((row) => {
        if (!row || typeof row !== "object") {
          return;
        }
        const tr = document.createElement("tr");
        const groupCell = document.createElement("td");
        groupCell.textContent = row["Nhóm nội dung"] || "";
        const contentCell = document.createElement("td");
        contentCell.textContent = row["Nội dung chính"] || "";
        tr.append(groupCell, contentCell);
        tbody.appendChild(tr);
      });

      table.append(thead, tbody);
      tableWrapper.appendChild(table);
      item.appendChild(tableWrapper);
    }

    summaryResultsEl.appendChild(item);
    renderedAny = true;
  });

  summaryResultsEl.classList.toggle("empty", !renderedAny);
  if (summaryMetaEl) {
    summaryMetaEl.textContent = `${summaries.length} file(s) tóm tắt.`;
  }
  lastSummaryPayload = payload;
  lastSummaryText = buildSummaryText(payload);
  updateActionState();
}

function removeSelectedFile(index) {
  const dt = new DataTransfer();
  const files = fileInput.files;
  for (let i = 0; i < files.length; i++) {
    if (i !== index) {
      dt.items.add(files[i]);
    }
  }
  fileInput.files = dt.files;
  renderFileCards(Array.from(fileInput.files));
}

function renderFileCards(files) {
  clearPreviews();

  if (!files.length) {
    setStatus("Chưa chọn file nào.", "idle");
    return;
  }

  if (files.length > 10) {
    setStatus(`Lỗi: Chỉ được chọn tối đa 10 file (Hiện đang chọn ${files.length} file).`, "idle");
    return;
  }

  const maxSingleSize = 10 * 1024 * 1024; // 10MB
  const hasTooLargeFile = files.some(file => file.size > maxSingleSize);
  if (hasTooLargeFile) {
    setStatus("Lỗi: Dung lượng của mỗi file không được vượt quá 10MB.", "idle");
    return;
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const maxTotalSize = 15 * 1024 * 1024; // 15MB
  if (totalSize > maxTotalSize) {
    setStatus(`Lỗi: Tổng dung lượng các file (${humanSize(totalSize)}) vượt quá giới hạn 15MB.`, "idle");
    return;
  }

  setStatus(`${files.length} file đã sẵn sàng để OCR.`, "active");

  files.forEach((file, index) => {
    const url = URL.createObjectURL(file);
    previewUrls.push(url);

    const card = document.createElement("article");
    card.className = "file-card";

    // Close / delete button
    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "btn-remove-file";
    deleteBtn.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
    `;
    deleteBtn.title = "Xóa file này khỏi danh sách";
    deleteBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      removeSelectedFile(index);
    });

    const preview = document.createElement("div");
    preview.className = "file-preview";

    if (file.type.startsWith("image/")) {
      const img = document.createElement("img");
      img.src = url;
      img.alt = file.name;
      preview.appendChild(img);
    } else if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
      const iframe = document.createElement("iframe");
      iframe.src = url;
      iframe.title = file.name;
      preview.appendChild(iframe);
    } else if (file.name.toLowerCase().endsWith(".docx")) {
      const placeholder = document.createElement("div");
      placeholder.className = "placeholder";
      placeholder.textContent = "Không hỗ trợ xem trước file Word. Bấm Chạy OCR để trích xuất text.";
      preview.appendChild(placeholder);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "placeholder";
      placeholder.textContent = "Không có chế độ xem trước cho định dạng này.";
      preview.appendChild(placeholder);
    }

    const meta = document.createElement("div");
    meta.className = "file-meta";
    meta.innerHTML = `
      <strong>${file.name}</strong>
      <span>${file.type || "unknown type"} · ${humanSize(file.size)}</span>
    `;

    card.append(deleteBtn, preview, meta);
    fileList.appendChild(card);
  });
}

function renderResults(payload) {
  resultsEl.classList.remove("empty");
  resultsEl.innerHTML = "";

  const results = Array.isArray(payload?.results) ? payload.results : [];
  if (!results.length) {
    resultsEl.classList.add("empty");
    resultsEl.innerHTML = `
      <div class="empty-state-content">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="empty-icon"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <p>Không có kết quả OCR.</p>
      </div>
    `;
    resultMetaEl.textContent = "0 file.";
    lastOcrText = "";
    lastOcrPayload = null;
    lastSummaryPayload = null;
    clearSummaryPreview();
    updateActionState();
    return;
  }

  let hasRenderedContent = false;
  const textChunks = [];
  const importTypeLabel = payload?.import_type_label || getImportTypeLabel(payload?.import_type);

  results.forEach((fileResult) => {
    const item = document.createElement("article");
    item.className = "result-item";

    const title = document.createElement("div");
    title.className = "result-title";

    const left = document.createElement("span");
    left.textContent = fileResult.filename || "untitled";

    const right = document.createElement("span");
    right.textContent = fileResult.status || "unknown";

    title.append(left, right);
    item.appendChild(title);

    const pages = Array.isArray(fileResult.pages) ? fileResult.pages : [];
    if (pages.length) {
      const pageTexts = [];
      pages.forEach((page) => {
        const pageBlock = document.createElement("div");
        pageBlock.className = "page-block";

        const pageLabel = document.createElement("div");
        pageLabel.className = "result-page-label";
        pageLabel.textContent = `Trang ${page.page_number ?? "?"}`;

        const pre = document.createElement("pre");
        pre.textContent = page.text || "(trống)";

        // Copy button
        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "btn-copy-text";
        copyBtn.innerHTML = `
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          <span>Sao chép</span>
        `;
        copyBtn.addEventListener("click", () => {
          navigator.clipboard.writeText(page.text || "").then(() => {
            copyBtn.classList.add("success");
            copyBtn.innerHTML = `
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              <span>Đã chép</span>
            `;
            setTimeout(() => {
              copyBtn.classList.remove("success");
              copyBtn.innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                <span>Sao chép</span>
              `;
            }, 2000);
          });
        });

        pageBlock.append(pageLabel, pre, copyBtn);
        item.appendChild(pageBlock);
        hasRenderedContent = true;
        const pageText = page.text || "(trống)";
        pageTexts.push(`-------------------------------- trang ${page.page_number ?? "?"} -----------------------------\n${pageText}`);
      });
      textChunks.push(`File: ${fileResult.filename || "untitled"}\n${pageTexts.join("\n\n")}`);
    } else if (fileResult.message) {
      const pageBlock = document.createElement("div");
      pageBlock.className = "page-block";
      const pre = document.createElement("pre");
      pre.textContent = fileResult.message;
      pageBlock.appendChild(pre);
      item.appendChild(pageBlock);
      hasRenderedContent = true;
      textChunks.push(`File: ${fileResult.filename || "untitled"}\nLỖI: ${fileResult.message}`);
    }

    resultsEl.appendChild(item);
  });

  resultMetaEl.textContent = `${results.length} file(s) processed · ${importTypeLabel}`;
  lastOcrPayload = payload;
  lastOcrText = textChunks.join("\n\n---\n\n");
  lastDownloadOcrTxtName = `ocr-goc-${new Date().toISOString().replace(/[:.]/g, "-")}.txt`;
  lastDownloadOcrXlsxName = `ocr-goc-${new Date().toISOString().replace(/[:.]/g, "-")}.xlsx`;
  lastDownloadSummaryTxtName = `tom-tat-ai-${new Date().toISOString().replace(/[:.]/g, "-")}.txt`;
  lastDownloadSummaryXlsxName = `tom-tat-ai-${new Date().toISOString().replace(/[:.]/g, "-")}.xlsx`;
  clearSummaryPreview();
  updateActionState();

  if (!hasRenderedContent) {
    resultsEl.classList.add("empty");
    resultsEl.innerHTML = `
      <div class="empty-state-content">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="empty-icon"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <p>OCR hoàn thành nhưng không trích xuất được văn bản nào.</p>
      </div>
    `;
  }
}

function parseMaybeJson(text) {
  try {
    return { data: JSON.parse(text), isJson: true };
  } catch {
    return { data: text, isJson: false };
  }
}

// Drag & Drop event bindings
if (dropzoneLabel) {
  ["dragenter", "dragover"].forEach((eventName) => {
    dropzoneLabel.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzoneLabel.classList.add("dragover");
    }, false);
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzoneLabel.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzoneLabel.classList.remove("dragover");
    }, false);
  });

  dropzoneLabel.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      fileInput.files = files;
      renderFileCards(Array.from(fileInput.files));
    }
  });
}

fileInput.addEventListener("change", () => {
  renderFileCards(Array.from(fileInput.files || []));
});

clearBtn.addEventListener("click", () => {
  fileInput.value = "";
  if (importTypeSelect) {
    importTypeSelect.value = "clear";
  }
  clearPreviews();
  resultsEl.className = "results empty";
  resultsEl.innerHTML = `
    <div class="empty-state-content">
      <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="empty-icon"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <p>Chọn file và bấm nút "Chạy OCR" để bắt đầu nhận diện văn bản.</p>
    </div>
  `;
  clearSummaryPreview();
  setStatus("Chưa chọn file nào.", "idle");
  resultMetaEl.textContent = "Chưa có kết quả.";
  lastOcrText = "";
  lastOcrPayload = null;
  lastSummaryPayload = null;
  if (layoutPreserveCheckbox) {
    layoutPreserveCheckbox.checked = true;
  }
  updateActionState();
});

downloadOcrTxtBtn.addEventListener("click", () => {
  if (!lastOcrText) {
    return;
  }

  const blob = new Blob([lastOcrText], { type: "text/plain;charset=utf-8" });
  triggerDownload(blob, lastDownloadOcrTxtName);
  setStatus("Đã tải OCR gốc (TXT).", "active");
});

downloadOcrXlsxBtn.addEventListener("click", async () => {
  if (!lastOcrPayload) {
    return;
  }

  downloadOcrXlsxBtn.disabled = true;
  setStatus("Đang xuất OCR gốc (XLSX)...", "running");

  try {
    const response = await fetch("/export/xlsx", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...lastOcrPayload,
      }),
    });

    if (!response.ok) {
      const responseText = await response.text();
      const parsed = parseMaybeJson(responseText);
      const payload = parsed.isJson ? parsed.data : { raw: responseText };
      const message = parsed.isJson
        ? (payload.error || payload.message || "Excel export failed.")
        : "Server returned a non-JSON error page. Check backend logs.";
      setStatus("Không xuất được OCR gốc (XLSX).", "active");
      console.error(message);
      return;
    }

    const blob = await response.blob();
    const filename = filenameFromContentDisposition(response.headers.get("Content-Disposition"))
      || lastDownloadOcrXlsxName;
    triggerDownload(blob, filename);
    setStatus("Đã xuất OCR gốc (XLSX).", "active");
  } catch (error) {
    setStatus("Không xuất được OCR gốc (XLSX).", "active");
    console.error(error);
  } finally {
    updateActionState();
  }
});

downloadSummaryTxtBtn.addEventListener("click", () => {
  if (!lastSummaryText) {
    return;
  }

  const blob = new Blob([lastSummaryText], { type: "text/plain;charset=utf-8" });
  triggerDownload(blob, lastDownloadSummaryTxtName);
  setStatus("Đã tải tóm tắt AI (TXT).", "active");
});

downloadSummaryXlsxBtn.addEventListener("click", async () => {
  if (!lastSummaryPayload) {
    return;
  }

  downloadSummaryXlsxBtn.disabled = true;
  setStatus("Đang xuất tóm tắt AI (XLSX)...", "running");

  try {
    const response = await fetch("/export/summary-xlsx", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...lastOcrPayload,
        summary_results: lastSummaryPayload?.summaries || null,
      }),
    });

    if (!response.ok) {
      const responseText = await response.text();
      const parsed = parseMaybeJson(responseText);
      const payload = parsed.isJson ? parsed.data : { raw: responseText };
      const message = parsed.isJson
        ? (payload.error || payload.message || "Summary Excel export failed.")
        : "Server returned a non-JSON error page. Check backend logs.";
      setStatus("Không xuất được tóm tắt AI (XLSX).", "active");
      console.error(message);
      return;
    }

    const blob = await response.blob();
    const filename = filenameFromContentDisposition(response.headers.get("Content-Disposition"))
      || lastDownloadSummaryXlsxName;
    triggerDownload(blob, filename);
    setStatus("Đã xuất tóm tắt AI (XLSX).", "active");
  } catch (error) {
    setStatus("Không xuất được tóm tắt AI (XLSX).", "active");
    console.error(error);
  } finally {
    updateActionState();
  }
});

runSummaryBtn.addEventListener("click", async () => {
  if (!lastOcrPayload) {
    return;
  }

  const originalHtml = runSummaryBtn.innerHTML;
  runSummaryBtn.disabled = true;
  runSummaryBtn.innerHTML = `<span class="spinner"></span> <span>Đang tóm tắt...</span>`;
  setStatus("Đang chạy tóm tắt AI...", "running");

  try {
    const response = await fetch("/summarize", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(lastOcrPayload),
    });

    const responseText = await response.text();
    const parsed = parseMaybeJson(responseText);
    const payload = parsed.isJson ? parsed.data : { raw: responseText };

    if (!response.ok) {
      setStatus("Không chạy được tóm tắt AI.", "active");
      const message = parsed.isJson
        ? (payload.error || payload.message || "Summary request failed.")
        : "Server returned a non-JSON error page. Check backend logs.";
      console.error(message);
      return;
    }

    renderSummaryResults(payload);
    setStatus("Đã tạo bảng tóm tắt AI.", "active");
  } catch (error) {
    setStatus("Không chạy được tóm tắt AI.", "active");
    console.error(error);
  } finally {
    runSummaryBtn.innerHTML = originalHtml;
    updateActionState();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const files = Array.from(fileInput.files || []);
  if (!files.length) {
    setStatus("Hãy chọn ít nhất một file.", "idle");
    return;
  }

  if (files.length > 10) {
    setStatus("Chỉ được phép chọn tối đa 10 file mỗi lượt.", "idle");
    return;
  }

  const maxSingleSize = 10 * 1024 * 1024; // 10MB
  const hasTooLargeFile = files.some(file => file.size > maxSingleSize);
  if (hasTooLargeFile) {
    setStatus("Mỗi file tải lên không được vượt quá 10MB.", "idle");
    return;
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const maxTotalSize = 15 * 1024 * 1024; // 15MB
  if (totalSize > maxTotalSize) {
    setStatus(`Tổng dung lượng file (${humanSize(totalSize)}) vượt quá giới hạn 15MB.`, "idle");
    return;
  }

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("import_type", importTypeSelect?.value || "clear");
  formData.append("layout_preserve", layoutPreserveCheckbox?.checked ? "true" : "false");

  const originalSubmitHtml = submitBtn.innerHTML;
  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span class="spinner"></span> <span>Đang xử lý OCR...</span>`;

  clearBtn.disabled = true;
  downloadOcrTxtBtn.disabled = true;
  downloadOcrXlsxBtn.disabled = true;
  runSummaryBtn.disabled = true;
  downloadSummaryTxtBtn.disabled = true;
  downloadSummaryXlsxBtn.disabled = true;
  
  const selectedImportType = importTypeSelect?.value || "clear";
  setStatus(getOcrRunStatusMessage(selectedImportType), "running");

  try {
    const response = await fetch("/ocr", {
      method: "POST",
      body: formData,
    });

    const responseText = await response.text();
    const parsed = parseMaybeJson(responseText);
    const payload = parsed.isJson ? parsed.data : { raw: responseText };

    if (!response.ok) {
      resultsEl.className = "results empty";
      resultsEl.innerHTML = `
        <div class="empty-state-content">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="empty-icon"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          <p>${parsed.isJson ? (payload.error || payload.message || "OCR request failed.") : "Server returned a non-JSON error page."}</p>
        </div>
      `;
      resultMetaEl.textContent = "Yêu cầu thất bại.";
      setStatus("Có lỗi khi gọi OCR.", "idle");
      lastOcrPayload = null;
      return;
    }

    renderResults(payload);
    setStatus(`OCR xong ở chế độ ${getImportTypeLabel(payload?.import_type)}.`, "active");
  } catch (error) {
    resultsEl.className = "results empty";
    resultsEl.innerHTML = `
      <div class="empty-state-content">
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" class="empty-icon"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
        <p>${error?.message || "Unknown error."}</p>
      </div>
    `;
    resultMetaEl.textContent = "Yêu cầu thất bại.";
    setStatus("Không gọi được backend.", "idle");
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalSubmitHtml;
    clearBtn.disabled = false;
    updateActionState();
  }
});
