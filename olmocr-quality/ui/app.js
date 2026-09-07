const $ = (id) => document.getElementById(id);
let selectedFile = null,
  current = null,
  ready = false,
  busy = false,
  loaded = null,
  preview = null;
const labels = {
  running: "Đang OCR",
  done: "Hoàn tất",
  failed: "Không hoàn tất",
};
async function api(url, options) {
  const r = await fetch(url, options);
  const value = await r.json();
  if (!r.ok) throw new Error(value.error || "Không kết nối được giao diện.");
  return value;
}
function notice(text = "") {
  $("notice").textContent = text;
  $("notice").hidden = !text;
}
function controls() {
  $("run").disabled = !selectedFile || !ready || busy;
  $("sample").disabled = !ready || busy;
  $("file").disabled = busy;
  $("run").textContent = busy ? "Đang xử lý…" : "Bắt đầu OCR";
}
function showPdf(url) {
  $("pdf").src = url;
  $("pdf").hidden = false;
  $("pdf-empty").hidden = true;
  $("open-pdf").href = url;
  $("open-pdf").hidden = false;
}
function clearResult() {
  $("result").hidden = true;
  $("result").textContent = "";
  $("result-empty").hidden = false;
  for (const id of ["md", "jsonl"]) $(id).hidden = true;
  $("copy").disabled = true;
  loaded = null;
}
function choose(file) {
  if (!file || busy) return;
  if (!/\.pdf$/i.test(file.name)) {
    notice("Vui lòng chọn tệp PDF.");
    return;
  }
  if (file.size > 100 * 1024 * 1024) {
    notice("Vui lòng chọn PDF nhỏ hơn 100 MB.");
    return;
  }
  notice();
  selectedFile = file;
  current = null;
  clearResult();
  $("file-label").textContent = file.name;
  $("title").textContent = file.name;
  $("status").textContent = "Sẵn sàng. Bấm Bắt đầu OCR để xử lý.";
  $("duration").textContent = "";
  if (preview) URL.revokeObjectURL(preview);
  preview = URL.createObjectURL(file);
  showPdf(preview);
  controls();
}
$("file").addEventListener("change", (e) => choose(e.target.files[0]));
for (const event of ["dragenter", "dragover"])
  $("drop").addEventListener(event, (e) => {
    e.preventDefault();
    $("drop").classList.add("drag");
  });
for (const event of ["dragleave", "drop"])
  $("drop").addEventListener(event, (e) => {
    e.preventDefault();
    $("drop").classList.remove("drag");
    if (event === "drop") choose(e.dataTransfer.files[0]);
  });
async function start(sample) {
  notice();
  busy = true;
  controls();
  try {
    const job = await api(
      sample ? "/api/sample" : "/api/jobs",
      sample
        ? { method: "POST" }
        : {
            method: "POST",
            headers: {
              "Content-Type": "application/pdf",
              "X-File-Name": encodeURIComponent(selectedFile.name),
            },
            body: selectedFile,
          },
    );
    current = job.id;
    clearResult();
    showPdf(`/api/jobs/${current}/pdf`);
    await refresh();
  } catch (e) {
    notice(e.message);
    busy = false;
    controls();
  }
}
$("run").onclick = () => start(false);
$("sample").onclick = () => start(true);
$("copy").onclick = async () => {
  try {
    await navigator.clipboard.writeText($("result").textContent);
    $("copy").textContent = "Đã sao chép";
    setTimeout(() => ($("copy").textContent = "Sao chép"), 1800);
  } catch {
    notice("Trình duyệt không cho sao chép. Bạn có thể tải file .md.");
  }
};
async function refresh() {
  try {
    const [server, jobs] = await Promise.all([
      api("/api/health"),
      api("/api/jobs"),
    ]);
    ready = server.ready;
    busy = !!server.active;
    $("health").textContent = ready
      ? "Server OCR sẵn sàng"
      : "Server OCR chưa sẵn sàng";
    $("health").classList.toggle("ready", ready);
    controls();
    const focusedJob = $("history").contains(document.activeElement)
      ? document.activeElement.dataset.jobId
      : null;
    $("history").replaceChildren();
    for (const job of jobs) {
      const b = document.createElement("button");
      b.dataset.jobId = job.id;
      b.textContent = job.name;
      b.classList.toggle("selected", job.id === current);
      const s = document.createElement("span");
      s.textContent = `${labels[job.status]} · ${new Date(job.createdAt).toLocaleString("vi-VN")}`;
      b.append(s);
      b.onclick = () => {
        current = job.id;
        clearResult();
        showPdf(`/api/jobs/${current}/pdf`);
        void refresh();
      };
      $("history").append(b);
      if (job.id === focusedJob) b.focus({ preventScroll: true });
    }
    if (!jobs.length) $("history").textContent = "Chưa có tài liệu được xử lý.";
    if (!current && server.active && server.active !== "uploading") {
      current = server.active;
      showPdf(`/api/jobs/${current}/pdf`);
    }
    const job = jobs.find((j) => j.id === current);
    if (!job) return;
    $("title").textContent = job.name;
    $("status").textContent =
      job.status === "running"
        ? "Đang đọc các trang. Bạn có thể xem tiến trình trong nhật ký."
        : job.status === "done"
          ? "Đã tạo Markdown và JSONL. Đối chiếu với bản gốc trước khi sử dụng."
          : job.error;
    $("log").textContent = job.log || "Đang khởi động pipeline…";
    const seconds = Math.round(
      ((job.finishedAt ? new Date(job.finishedAt) : new Date()) -
        new Date(job.createdAt)) /
        1000,
    );
    $("duration").textContent = `${seconds} giây`;
    if (job.status === "done" && loaded !== job.id) {
      const id = job.id;
      const r = await fetch(`/api/jobs/${id}/markdown`);
      if (!r.ok) throw new Error("Không đọc được kết quả OCR.");
      const text = await r.text();
      if (current !== id) return;
      $("result").textContent = text;
      $("result").hidden = false;
      $("result-empty").hidden = true;
      $("copy").disabled = false;
      for (const [element, kind] of [
        ["md", "markdown"],
        ["jsonl", "jsonl"],
      ]) {
        $(element).href = `/api/jobs/${id}/${kind}?download=1`;
        $(element).hidden = false;
      }
      loaded = id;
    }
  } catch (e) {
    $("health").textContent = "Mất kết nối giao diện";
    ready = false;
    controls();
    notice(e.message);
  }
}
await refresh();
setInterval(() => void refresh(), 3000);
