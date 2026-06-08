const fileInput = document.getElementById("files");
const fileList = document.getElementById("file-list");
const form = document.getElementById("ocr-form");
const submitBtn = document.getElementById("submit-btn");
const clearBtn = document.getElementById("clear-btn");
const downloadBtn = document.getElementById("download-btn");
const downloadXlsxBtn = document.getElementById("download-xlsx-btn");
const importTypeSelect = document.getElementById("import-type");
const useLlmCheckbox = document.getElementById("use-llm");
const includeSummaryCheckbox = document.getElementById("include-summary");
const excelOptionsEl = document.getElementById("excel-options");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const resultMetaEl = document.getElementById("result-meta");
const layoutPreserveCheckbox = document.getElementById("layout-preserve");

let previewUrls = [];
let lastOcrText = "";
let lastOcrPayload = null;
let lastDownloadName = "ocr-result.txt";
let lastDownloadXlsxName = "ocr-result.xlsx";

function getImportTypeLabel(value) {
  if (value === "complex_llm") {
    return "PhÃ¡Â»Â©c tÃ¡ÂºÂ¡p + LLM (chÃ¡ÂºÂ­m nhÃ¡ÂºÂ¥t)";
  }
  return "RÃƒÂµ rÃƒÂ ng (nhanh)";
}

function getOcrRunStatusMessage(value) {
  if (value === "complex_llm") {
    return "Dang OCR che do phuc tap + LLM... vui long cho.";
  }
  return "Dang OCR che do nhanh... vui long cho.";
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

function showExcelOptions(show) {
  if (!excelOptionsEl) {
    return;
  }

  excelOptionsEl.classList.toggle("hidden", !show);
}

function renderFileCards(files) {
  clearPreviews();

  if (!files.length) {
    statusEl.textContent = "ChÃ†Â°a chÃ¡Â»Ân file nÃƒÂ o.";
    return;
  }

  if (files.length > 10) {
    statusEl.textContent = `LÃ¡Â»â€”i: ChÃ¡Â»â€° Ã„â€˜Ã†Â°Ã¡Â»Â£c chÃ¡Â»Ân tÃ¡Â»â€˜i Ã„â€˜a 10 file (HiÃ¡Â»â€¡n Ã„â€˜ang chÃ¡Â»Ân ${files.length} file).`;
    return;
  }

  const maxSingleSize = 10 * 1024 * 1024; // 10MB
  const hasTooLargeFile = files.some(file => file.size > maxSingleSize);
  if (hasTooLargeFile) {
    statusEl.textContent = "LÃ¡Â»â€”i: Dung lÃ†Â°Ã¡Â»Â£ng cÃ¡Â»Â§a mÃ¡Â»â€”i file khÃƒÂ´ng Ã„â€˜Ã†Â°Ã¡Â»Â£c vÃ†Â°Ã¡Â»Â£t quÃƒÂ¡ 10MB.";
    return;
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const maxTotalSize = 15 * 1024 * 1024; // 15MB
  if (totalSize > maxTotalSize) {
    statusEl.textContent = `LÃ¡Â»â€”i: TÃ¡Â»â€¢ng dung lÃ†Â°Ã¡Â»Â£ng cÃƒÂ¡c file (${humanSize(totalSize)}) vÃ†Â°Ã¡Â»Â£t quÃƒÂ¡ giÃ¡Â»â€ºi hÃ¡ÂºÂ¡n 15MB.`;
    return;
  }

  statusEl.textContent = `${files.length} file Ã„â€˜ÃƒÂ£ sÃ¡ÂºÂµn sÃƒÂ ng Ã„â€˜Ã¡Â»Æ’ OCR.`;

  files.forEach((file) => {
    const url = URL.createObjectURL(file);
    previewUrls.push(url);

    const card = document.createElement("article");
    card.className = "file-card";

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
      placeholder.textContent = "KhÃƒÂ´ng hÃ¡Â»â€” trÃ¡Â»Â£ xem trÃ†Â°Ã¡Â»â€ºc file Word. BÃ¡ÂºÂ¥m Run OCR Ã„â€˜Ã¡Â»Æ’ trÃƒÂ­ch xuÃ¡ÂºÂ¥t text.";
      preview.appendChild(placeholder);
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "placeholder";
      placeholder.textContent = "Preview not available for this file type.";
      preview.appendChild(placeholder);
    }

    const meta = document.createElement("div");
    meta.className = "file-meta";
    meta.innerHTML = `
      <strong>${file.name}</strong>
      <span>${file.type || "unknown type"} Ã‚Â· ${humanSize(file.size)}</span>
    `;

    card.append(preview, meta);
    fileList.appendChild(card);
  });
}

function renderResults(payload) {
  resultsEl.classList.remove("empty");
  resultsEl.innerHTML = "";

  const results = Array.isArray(payload?.results) ? payload.results : [];
  if (!results.length) {
    resultsEl.classList.add("empty");
    resultsEl.textContent = "KhÃƒÂ´ng cÃƒÂ³ kÃ¡ÂºÂ¿t quÃ¡ÂºÂ£ OCR.";
    resultMetaEl.textContent = "0 file.";
    lastOcrText = "";
    lastOcrPayload = null;
    downloadBtn.disabled = true;
    downloadXlsxBtn.disabled = true;
    showExcelOptions(false);
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
        pageLabel.textContent = `Page ${page.page_number ?? "?"}`;

        const pre = document.createElement("pre");
        pre.textContent = page.text || "(empty)";

        pageBlock.append(pageLabel, pre);
        item.appendChild(pageBlock);
        hasRenderedContent = true;
        const pageText = page.text || "(empty)";
        pageTexts.push(`Page ${page.page_number ?? "?"}\n${pageText}`);
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
      textChunks.push(`File: ${fileResult.filename || "untitled"}\nERROR: ${fileResult.message}`);
    }

    resultsEl.appendChild(item);
  });

  resultMetaEl.textContent = `${results.length} file(s) processed Ã‚Â· ${importTypeLabel}`;
  lastOcrPayload = payload;
  lastOcrText = textChunks.join("\n\n---\n\n");
  lastDownloadName = `ocr-result-${new Date().toISOString().replace(/[:.]/g, "-")}.txt`;
  lastDownloadXlsxName = `ocr-result-${new Date().toISOString().replace(/[:.]/g, "-")}.xlsx`;
  downloadBtn.disabled = !lastOcrText;
  downloadXlsxBtn.disabled = !lastOcrPayload;
  showExcelOptions(Boolean(lastOcrPayload));

  if (!hasRenderedContent) {
    resultsEl.classList.add("empty");
    resultsEl.textContent = "OCR finished but returned no text.";
  }
}

function parseMaybeJson(text) {
  try {
    return { data: JSON.parse(text), isJson: true };
  } catch {
    return { data: text, isJson: false };
  }
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
  resultsEl.textContent = "ChÃ¡Â»Ân file rÃ¡Â»â€œi bÃ¡ÂºÂ¥m Run OCR Ã„â€˜Ã¡Â»Æ’ xem text Ã¡Â»Å¸ Ã„â€˜ÃƒÂ¢y.";
  statusEl.textContent = "ChÃ†Â°a chÃ¡Â»Ân file nÃƒÂ o.";
  resultMetaEl.textContent = "ChÃ†Â°a cÃƒÂ³ kÃ¡ÂºÂ¿t quÃ¡ÂºÂ£.";
  lastOcrText = "";
  lastOcrPayload = null;
  downloadBtn.disabled = true;
  downloadXlsxBtn.disabled = true;
  showExcelOptions(false);
  if (useLlmCheckbox) {
    useLlmCheckbox.checked = false;
  }
  if (includeSummaryCheckbox) {
    includeSummaryCheckbox.checked = false;
  }
  if (layoutPreserveCheckbox) {
    layoutPreserveCheckbox.checked = true;
  }
});

downloadBtn.addEventListener("click", () => {
  if (!lastOcrText) {
    return;
  }

  const blob = new Blob([lastOcrText], { type: "text/plain;charset=utf-8" });
  triggerDownload(blob, lastDownloadName);
});

downloadXlsxBtn.addEventListener("click", async () => {
  if (!lastOcrPayload) {
    return;
  }

  downloadXlsxBtn.disabled = true;
  const useLlm = Boolean(useLlmCheckbox?.checked);
  const includeSummary = Boolean(includeSummaryCheckbox?.checked);
  statusEl.textContent = includeSummary
    ? "Dang tao file Excel va tom tat bang LLM..."
    : "Dang tao file Excel...";

  try {
    const response = await fetch("/export/xlsx", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...lastOcrPayload,
        use_llm: useLlm,
        include_summary: includeSummary,
      }),
    });

    if (!response.ok) {
      const responseText = await response.text();
      const parsed = parseMaybeJson(responseText);
      const payload = parsed.isJson ? parsed.data : { raw: responseText };
      const message = parsed.isJson
        ? (payload.error || payload.message || "Excel export failed.")
        : "Server returned a non-JSON error page. Check backend logs.";
      statusEl.textContent = "KhÃƒÂ´ng xuÃ¡ÂºÂ¥t Ã„â€˜Ã†Â°Ã¡Â»Â£c Excel.";
      console.error(message);
      return;
    }

    const blob = await response.blob();
    const filename = filenameFromContentDisposition(response.headers.get("Content-Disposition"))
      || lastDownloadXlsxName;
    triggerDownload(blob, filename);
    statusEl.textContent = "Ã„ÂÃƒÂ£ tÃ¡ÂºÂ£i Excel.";
  } catch (error) {
    statusEl.textContent = "KhÃƒÂ´ng xuÃ¡ÂºÂ¥t Ã„â€˜Ã†Â°Ã¡Â»Â£c Excel.";
    console.error(error);
  } finally {
    downloadXlsxBtn.disabled = !lastOcrPayload;
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const files = Array.from(fileInput.files || []);
  if (!files.length) {
    statusEl.textContent = "HÃƒÂ£y chÃ¡Â»Ân ÃƒÂ­t nhÃ¡ÂºÂ¥t mÃ¡Â»â„¢t file.";
    return;
  }

  if (files.length > 10) {
    statusEl.textContent = "ChÃ¡Â»â€° Ã„â€˜Ã†Â°Ã¡Â»Â£c phÃƒÂ©p chÃ¡Â»Ân tÃ¡Â»â€˜i Ã„â€˜a 10 file mÃ¡Â»â€”i lÃ†Â°Ã¡Â»Â£t.";
    return;
  }

  const maxSingleSize = 10 * 1024 * 1024; // 10MB
  const hasTooLargeFile = files.some(file => file.size > maxSingleSize);
  if (hasTooLargeFile) {
    statusEl.textContent = "MÃ¡Â»â€”i file tÃ¡ÂºÂ£i lÃƒÂªn khÃƒÂ´ng Ã„â€˜Ã†Â°Ã¡Â»Â£c vÃ†Â°Ã¡Â»Â£t quÃƒÂ¡ 10MB.";
    return;
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const maxTotalSize = 15 * 1024 * 1024; // 15MB
  if (totalSize > maxTotalSize) {
    statusEl.textContent = `TÃ¡Â»â€¢ng dung lÃ†Â°Ã¡Â»Â£ng file (${humanSize(totalSize)}) vÃ†Â°Ã¡Â»Â£t quÃƒÂ¡ giÃ¡Â»â€ºi hÃ¡ÂºÂ¡n 15MB.`;
    return;
  }

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("import_type", importTypeSelect?.value || "clear");
  formData.append("layout_preserve", layoutPreserveCheckbox?.checked ? "true" : "false");

  submitBtn.disabled = true;
  clearBtn.disabled = true;
  downloadBtn.disabled = true;
  const selectedImportType = importTypeSelect?.value || "clear";
  statusEl.textContent = getOcrRunStatusMessage(selectedImportType);

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
      resultsEl.textContent = parsed.isJson
        ? (payload.error || payload.message || "OCR request failed.")
        : "Server returned a non-JSON error page. Check backend logs.";
      resultMetaEl.textContent = "Request failed.";
      statusEl.textContent = "CÃƒÂ³ lÃ¡Â»â€”i khi gÃ¡Â»Âi OCR.";
      lastOcrPayload = null;
      downloadXlsxBtn.disabled = true;
      return;
    }

    renderResults(payload);
    statusEl.textContent = `OCR xong Ã¡Â»Å¸ chÃ¡ÂºÂ¿ Ã„â€˜Ã¡Â»â„¢ ${getImportTypeLabel(payload?.import_type)}.`;
  } catch (error) {
    resultsEl.className = "results empty";
    resultsEl.textContent = error?.message || "Unknown error.";
    resultMetaEl.textContent = "Request failed.";
    statusEl.textContent = "KhÃƒÂ´ng gÃ¡Â»Âi Ã„â€˜Ã†Â°Ã¡Â»Â£c backend.";
  } finally {
    submitBtn.disabled = false;
    clearBtn.disabled = false;
  }
});
