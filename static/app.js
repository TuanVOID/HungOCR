const fileInput = document.getElementById("files");
const fileList = document.getElementById("file-list");
const form = document.getElementById("ocr-form");
const submitBtn = document.getElementById("submit-btn");
const clearBtn = document.getElementById("clear-btn");
const downloadBtn = document.getElementById("download-btn");
const downloadXlsxBtn = document.getElementById("download-xlsx-btn");
const importTypeSelect = document.getElementById("import-type");
const useLlmCheckbox = document.getElementById("use-llm");
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
  return value === "complex" ? "Phức tạp (chậm)" : "Rõ ràng (nhanh)";
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
    statusEl.textContent = "Chưa chọn file nào.";
    return;
  }

  if (files.length > 10) {
    statusEl.textContent = `Lỗi: Chỉ được chọn tối đa 10 file (Hiện đang chọn ${files.length} file).`;
    return;
  }

  const maxSingleSize = 10 * 1024 * 1024; // 10MB
  const hasTooLargeFile = files.some(file => file.size > maxSingleSize);
  if (hasTooLargeFile) {
    statusEl.textContent = "Lỗi: Dung lượng của mỗi file không được vượt quá 10MB.";
    return;
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const maxTotalSize = 15 * 1024 * 1024; // 15MB
  if (totalSize > maxTotalSize) {
    statusEl.textContent = `Lỗi: Tổng dung lượng các file (${humanSize(totalSize)}) vượt quá giới hạn 15MB.`;
    return;
  }

  statusEl.textContent = `${files.length} file đã sẵn sàng để OCR.`;

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
      placeholder.textContent = "Không hỗ trợ xem trước file Word. Bấm Run OCR để trích xuất text.";
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
      <span>${file.type || "unknown type"} · ${humanSize(file.size)}</span>
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
    resultsEl.textContent = "Không có kết quả OCR.";
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

  resultMetaEl.textContent = `${results.length} file(s) processed · ${importTypeLabel}`;
  lastOcrPayload = payload;
  lastOcrText = textChunks.join("\n\n---\n\n");
  lastDownloadName = `ocr-result-${new Date().toISOString().replace(/[:.]/g, "-")}.txt`;
  lastDownloadXlsxName = `ocr-result-${new Date().toISOString().replace(/[:.]/g, "-")}.xlsx`;
  downloadBtn.disabled = !lastOcrText;
  downloadXlsxBtn.disabled = !lastOcrPayload;

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
  resultsEl.textContent = "Chọn file rồi bấm Run OCR để xem text ở đây.";
  statusEl.textContent = "Chưa chọn file nào.";
  resultMetaEl.textContent = "Chưa có kết quả.";
  lastOcrText = "";
  lastOcrPayload = null;
  downloadBtn.disabled = true;
  downloadXlsxBtn.disabled = true;
  showExcelOptions(false);
  if (useLlmCheckbox) {
    useLlmCheckbox.checked = false;
  }
  if (layoutPreserveCheckbox) {
    layoutPreserveCheckbox.checked = true;
  }
});

downloadBtn.addEventListener("click", () => {
  if (!lastOcrText) {
    return;
  }

  showExcelOptions(false);
  const blob = new Blob([lastOcrText], { type: "text/plain;charset=utf-8" });
  triggerDownload(blob, lastDownloadName);
});

downloadXlsxBtn.addEventListener("click", async () => {
  if (!lastOcrPayload) {
    return;
  }

  if (excelOptionsEl?.classList.contains("hidden")) {
    showExcelOptions(true);
    statusEl.textContent = "Chọn có dùng LLM nếu cần, rồi bấm Download Excel lần nữa.";
    return;
  }

  downloadXlsxBtn.disabled = true;
  const useLlm = Boolean(useLlmCheckbox?.checked);
  statusEl.textContent = useLlm ? "Đang tạo file Excel bằng LLM..." : "Đang tạo file Excel...";

  try {
    const response = await fetch("/export/xlsx", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...lastOcrPayload,
        use_llm: useLlm,
      }),
    });

    if (!response.ok) {
      const responseText = await response.text();
      const parsed = parseMaybeJson(responseText);
      const payload = parsed.isJson ? parsed.data : { raw: responseText };
      const message = parsed.isJson
        ? (payload.error || payload.message || "Excel export failed.")
        : "Server returned a non-JSON error page. Check backend logs.";
      statusEl.textContent = "Không xuất được Excel.";
      console.error(message);
      return;
    }

    const blob = await response.blob();
    const filename = filenameFromContentDisposition(response.headers.get("Content-Disposition"))
      || lastDownloadXlsxName;
    triggerDownload(blob, filename);
    statusEl.textContent = useLlm ? "Đã tải Excel bằng LLM." : "Đã tải Excel.";
  } catch (error) {
    statusEl.textContent = "Không xuất được Excel.";
    console.error(error);
  } finally {
    downloadXlsxBtn.disabled = !lastOcrPayload;
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const files = Array.from(fileInput.files || []);
  if (!files.length) {
    statusEl.textContent = "Hãy chọn ít nhất một file.";
    return;
  }

  if (files.length > 10) {
    statusEl.textContent = "Chỉ được phép chọn tối đa 10 file mỗi lượt.";
    return;
  }

  const maxSingleSize = 10 * 1024 * 1024; // 10MB
  const hasTooLargeFile = files.some(file => file.size > maxSingleSize);
  if (hasTooLargeFile) {
    statusEl.textContent = "Mỗi file tải lên không được vượt quá 10MB.";
    return;
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const maxTotalSize = 15 * 1024 * 1024; // 15MB
  if (totalSize > maxTotalSize) {
    statusEl.textContent = `Tổng dung lượng file (${humanSize(totalSize)}) vượt quá giới hạn 15MB.`;
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
  statusEl.textContent = selectedImportType === "complex"
    ? "Đang OCR chế độ phức tạp... vui lòng chờ."
    : "Đang OCR chế độ rõ ràng... vui lòng chờ.";

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
      statusEl.textContent = "Có lỗi khi gọi OCR.";
      lastOcrPayload = null;
      downloadXlsxBtn.disabled = true;
      return;
    }

    renderResults(payload);
    showExcelOptions(false);
    statusEl.textContent = `OCR xong ở chế độ ${getImportTypeLabel(payload?.import_type)}.`;
  } catch (error) {
    resultsEl.className = "results empty";
    resultsEl.textContent = error?.message || "Unknown error.";
    resultMetaEl.textContent = "Request failed.";
    statusEl.textContent = "Không gọi được backend.";
  } finally {
    submitBtn.disabled = false;
    clearBtn.disabled = false;
  }
});
