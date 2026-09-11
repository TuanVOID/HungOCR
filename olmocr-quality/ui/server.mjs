import http from "node:http";
import { createModelLifecycle } from "./model-lifecycle.mjs";
import {
  readFile,
  writeFile,
  mkdir,
  readdir,
  stat,
  copyFile,
} from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID, timingSafeEqual } from "node:crypto";
import { spawn } from "node:child_process";

const root = path.dirname(fileURLToPath(import.meta.url));
const container = process.env.OLMOCR_CONTAINER === "1";
const apiKey = process.env.OLMOCR_API_KEY || "";
if (container && apiKey.length < 32) throw new Error("OLMOCR_API_KEY must contain at least 32 characters.");
const jobsRoot = process.env.OLMOCR_JOBS_ROOT || path.join(root, "..", "ui-workspace");
await mkdir(jobsRoot, { recursive: true });
const jobs = new Map();
let active = null;
const model = createModelLifecycle(() => active !== null);
let checkingIdle = false;
const idleTimer = setInterval(() => {
  if (checkingIdle) return;
  checkingIdle = true;
  void model
    .tick()
    .catch(console.error)
    .finally(() => {
      checkingIdle = false;
    });
}, 1000);
idleTimer.unref();
const wslPath = (p) =>
  p
    .replaceAll("\\", "/")
    .replace(/^([A-Za-z]):/, (_, drive) => `/mnt/${drive.toLowerCase()}`);
const save = (job) =>
  writeFile(
    path.join(jobsRoot, job.id, "job.json"),
    JSON.stringify(job, null, 2),
  );
for (const entry of await readdir(jobsRoot)) {
  try {
    const job = JSON.parse(
      await readFile(path.join(jobsRoot, entry, "job.json"), "utf8"),
    );
    if (job.status === "running") {
      job.status = "failed";
      job.error = "Giao diện đã dừng khi OCR đang chạy. Hãy chạy lại tài liệu.";
      await save(job);
    }
    jobs.set(job.id, job);
  } catch (error) {
    console.warn("Skipped unavailable job:", entry, error.message);
  }
}
async function files(dir) {
  const result = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) result.push(...(await files(p)));
    else result.push(p);
  }
  return result;
}
async function execute(job) {
  try {
    job.log = "Đang nạp model OCR nếu cần…";
    await model.ensureReady();
    const dir = path.join(jobsRoot, job.id);
    const proc = spawn(
      container ? "bash" : "wsl.exe",
      container ? [path.join(root, "..", "ocr.sh"), path.join(dir, "output"), path.join(dir, "input.pdf")] : [
        "-d",
        "Ubuntu",
        "--",
        "bash",
        wslPath(path.join(root, "..", "ocr.sh")),
        wslPath(path.join(dir, "output")),
        wslPath(path.join(dir, "input.pdf")),
      ],
      { windowsHide: true },
    );
    let log = "";
    const append = (chunk) => {
      log = (log + chunk.toString("utf8")).slice(-60000);
      job.log = log;
    };
    proc.stdout.on("data", append);
    proc.stderr.on("data", append);
    const code = await new Promise((resolve, reject) => {
      proc.once("error", reject);
      proc.once("close", resolve);
    });
    if (code !== 0)
      throw new Error(
        "Pipeline OCR không hoàn tất. Xem nhật ký bên dưới và kiểm tra server.",
      );
    const output = await files(path.join(dir, "output"));
    job.markdown = output.find((p) => p.endsWith(".md"));
    job.jsonl = output.find((p) => p.endsWith(".jsonl"));
    if (!job.markdown || !job.jsonl)
      throw new Error(
        "Pipeline chưa tạo đủ Markdown và JSONL. Xem nhật ký để kiểm tra trang bị bỏ qua.",
      );
    job.status = "done";
  } catch (error) {
    job.status = "failed";
    job.error = error.message;
  } finally {
    job.finishedAt = new Date().toISOString();
    await save(job);
    active = null;
    model.touch();
  }
}
function json(res, status, data) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(data));
}
async function upload(req, destination) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 100 * 1024 * 1024) throw new Error("PDF vượt giới hạn 100 MB.");
    chunks.push(chunk);
  }
  const buffer = Buffer.concat(chunks);
  if (!buffer.subarray(0, 1024).includes(Buffer.from("%PDF-")))
    throw new Error("Tệp không có định dạng PDF hợp lệ.");
  await writeFile(destination, buffer);
  return size;
}
const publicJob = (job) => ({
  ...job,
  markdown: !!job.markdown,
  jsonl: !!job.jsonl,
});
const server = http.createServer(async (req, res) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("Cache-Control", "no-store");
  try {
    if (!container && !["127.0.0.1:8010", "localhost:8010"].includes(req.headers.host))
      return json(res, 403, { error: "Localhost only." });
    if (
      req.method === "POST" &&
      req.headers.origin &&
      !["http://localhost:8010", "http://127.0.0.1:8010"].includes(
        req.headers.origin,
      )
    )
      return json(res, 403, { error: "Origin rejected." });
    const url = new URL(req.url, "http://localhost:8010");
    if (container && !(req.method === "GET" && url.pathname === "/api/health")) {
      const supplied = Buffer.from(req.headers.authorization || "");
      const expected = Buffer.from(`Bearer ${apiKey}`);
      if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected))
        return json(res, 401, { error: "Unauthorized." });
    }
    if (req.method === "GET" && url.pathname === "/api/health")
      return json(res, 200, {
        ready: true,
        model_ready: model.state === "ready",
        model_state: model.state,
        idle_timeout_seconds: 300,
        active,
      });
    if (req.method === "GET" && url.pathname === "/api/jobs")
      return json(res, 200, [...jobs.values()].reverse().map(publicJob));
    if (
      req.method === "POST" &&
      ["/api/jobs", "/api/sample"].includes(url.pathname)
    ) {
      if (active)
        return json(res, 409, {
          error: "Một tài liệu đang được xử lý. Vui lòng chờ hoàn tất.",
        });
      active = "uploading";
      let job;
      try {
        const id = randomUUID();
        const dir = path.join(jobsRoot, id);
        await mkdir(dir);
        const name =
          url.pathname === "/api/sample"
            ? "test_OCR.pdf"
            : path
                .basename(
                  decodeURIComponent(
                    req.headers["x-file-name"] || "document.pdf",
                  ),
                )
                .slice(0, 200);
        const input = path.join(dir, "input.pdf");
        if (url.pathname === "/api/sample")
          await copyFile(
            path.join(root, "..", "..", "docling", "docs", "test_OCR.pdf"),
            input,
          );
        else await upload(req, input);
        job = {
          id,
          name,
          status: "running",
          createdAt: new Date().toISOString(),
          size: (await stat(input)).size,
          log: "",
        };
        jobs.set(id, job);
        await save(job);
        active = id;
        void execute(job).catch((error) => {
          active = null;
          console.error(error);
        });
        return json(res, 202, publicJob(job));
      } finally {
        if (!job) active = null;
      }
    }
    const match = url.pathname.match(
      /^\/api\/jobs\/([a-f0-9-]+)(?:\/(pdf|markdown|jsonl))?$/,
    );
    if (req.method === "GET" && match) {
      const job = jobs.get(match[1]);
      if (!job)
        return json(res, 404, { error: "Không tìm thấy lần xử lý này." });
      if (!match[2]) return json(res, 200, publicJob(job));
      const kind = match[2];
      const file =
        kind === "pdf" ? path.join(jobsRoot, job.id, "input.pdf") : job[kind];
      if (!file) return json(res, 404, { error: "Kết quả chưa sẵn sàng." });
      const body = await readFile(file);
      res.setHeader(
        "Content-Type",
        kind === "pdf" ? "application/pdf" : "text/plain; charset=utf-8",
      );
      if (url.searchParams.has("download"))
        res.setHeader(
          "Content-Disposition",
          `attachment; filename="result.${kind === "markdown" ? "md" : kind}"`,
        );
      res.end(body);
      return;
    }
    const staticFiles = {
      "/": "index.html",
      "/app.js": "app.js",
      "/style.css": "style.css",
    };
    if (req.method === "GET" && staticFiles[url.pathname]) {
      const ext = path.extname(staticFiles[url.pathname]);
      res.setHeader(
        "Content-Type",
        { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" }[
          ext
        ] + "; charset=utf-8",
      );
      res.end(await readFile(path.join(root, staticFiles[url.pathname])));
      return;
    }
    json(res, 404, { error: "Không tìm thấy trang." });
  } catch (error) {
    console.error(error);
    if (!res.headersSent) json(res, 400, { error: error.message });
    else res.end();
  }
});
server.listen(8010, container ? "0.0.0.0" : "127.0.0.1", () =>
  console.log("olmOCR UI: http://localhost:8010"),
);
