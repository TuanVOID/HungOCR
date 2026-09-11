import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { createWriteStream } from "node:fs";

// The container owns this process group, never a host PID or Docker socket.
export function linuxModelProcess(probe) {
  let child = null;
  const stop = async () => {
    const running = child;
    if (!running) return;
    const closed = new Promise((resolve) => running.once("close", resolve));
    const kill = (signal) => {
      try { process.kill(-running.pid, signal); }
      catch (error) { if (error.code !== "ESRCH") throw error; }
    };
    kill("SIGTERM");
    const timer = setTimeout(() => kill("SIGKILL"), 20000);
    try { await closed; } finally { clearTimeout(timer); if (child === running) child = null; }
  };
  const start = async () => {
    if (child) await stop();
    const log = createWriteStream("/data/vllm.log", { flags: "a" });
    const running = spawn("bash", ["/app/serve.sh"], { detached: true, stdio: ["ignore", "pipe", "pipe"] });
    child = running;
    let failure;
    running.stdout.pipe(log, { end: false });
    running.stderr.pipe(log, { end: false });
    running.once("error", (error) => { failure = error; });
    running.once("close", () => { log.end(); if (child === running) child = null; });
    try {
      const deadline = Date.now() + 600000;
      while (Date.now() < deadline) {
        if (failure) throw failure;
        if (child !== running) throw new Error("Model exited during loading; check /data/vllm.log.");
        if ((await probe())?.ready) return;
        await delay(2000);
      }
      throw new Error("Model load timed out after 10 minutes.");
    } catch (error) { await stop(); throw error; }
  };
  return { start, stop };
}
