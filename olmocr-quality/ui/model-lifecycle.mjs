import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";

export class ModelLifecycle {
  constructor({ probe, start, stop, busy, now = Date.now, idleMs = 300000 }) {
    Object.assign(this, { probe, start, stop, busy, now, idleMs });
    this.lastUsed = now();
    this.state = "unloaded";
    this.tail = Promise.resolve();
    this.counter = undefined;
  }
  serialize(action) {
    const result = this.tail.then(action);
    this.tail = result.catch(() => {});
    return result;
  }
  touch() {
    this.lastUsed = this.now();
  }
  ensureReady() {
    return this.serialize(async () => {
      this.touch();
      if ((await this.probe())?.ready) {
        this.state = "ready";
        return;
      }
      this.state = "loading";
      try {
        await this.start();
        this.state = "ready";
      } catch (error) {
        this.state = "error";
        throw error;
      } finally {
        this.touch();
      }
    });
  }
  tick() {
    return this.serialize(async () => {
      if (this.busy()) {
        this.touch();
        return;
      }
      const observation = await this.probe();
      // Unknown metrics must never cause an active model to be stopped.
      if (!observation) return;
      if (!observation.ready) {
        this.state = "unloaded";
        return;
      }
      this.state = "ready";
      if (
        observation.running ||
        (this.counter !== undefined && this.counter !== observation.counter)
      )
        this.touch();
      this.counter = observation.counter;
      if (this.busy() || this.now() - this.lastUsed < this.idleMs) return;
      this.state = "unloading";
      try {
        await this.stop();
        this.state = "unloaded";
      } catch (error) {
        this.state = "error";
        this.touch();
        throw error;
      }
    });
  }
}

function wsl(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      "wsl.exe",
      ["-d", "Ubuntu", "-u", "root", "--", ...args],
      { windowsHide: true },
    );
    let error = "";
    child.stderr.on("data", (chunk) => {
      error = (error + chunk).slice(-2000);
    });
    child.once("error", reject);
    child.once("close", (code) =>
      code === 0
        ? resolve()
        : reject(new Error(`OCR model service failed (${code}): ${error}`)),
    );
  });
}

export async function probeModel() {
  try {
    const response = await fetch("http://127.0.0.1:8000/metrics", {
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) return null;
    const metrics = await response.text();
    const values = (name) =>
      [
        ...metrics.matchAll(
          new RegExp(`^${name}\\{[^\\n]*\\} ([0-9.e+\\-]+)$`, "gm"),
        ),
      ].map((match) => Number(match[1]));
    const running = values("vllm:num_requests_running");
    const waiting = values("vllm:num_requests_waiting");
    const completed = values("vllm:request_success_total");
    if (!running.length || !waiting.length) return null;
    return {
      ready: true,
      running: [...running, ...waiting].some((n) => n > 0),
      counter: completed.reduce((a, b) => a + b, 0),
    };
  } catch (error) {
    return error.cause?.code === "ECONNREFUSED" ? { ready: false } : null;
  }
}

export function createModelLifecycle(busy) {
  return new ModelLifecycle({
    busy,
    probe: probeModel,
    stop: () => wsl(["systemctl", "stop", "olmocr-vllm.service"]),
    start: async () => {
      // Keep WSL alive throughout loading and while the service is active.
      const keeper = spawn(
        "wsl.exe",
        [
          "-d",
          "Ubuntu",
          "-u",
          "root",
          "--",
          "bash",
          "/mnt/f/.VibeCoding/19.HungOCR/olmocr-quality/keep-alive.sh",
        ],
        { windowsHide: true, stdio: "ignore" },
      );
      let spawnError;
      keeper.once("error", (error) => {
        spawnError = error;
      });
      const deadline = Date.now() + 600000;
      while (Date.now() < deadline) {
        if (spawnError) throw spawnError;
        if ((await probeModel())?.ready) return;
        if (keeper.exitCode !== null)
          throw new Error("Không khởi động được model OCR. Kiểm tra vllm.log.");
        await delay(2000);
      }
      await wsl(["systemctl", "stop", "olmocr-vllm.service"]);
      throw new Error("Nạp model OCR quá thời gian 10 phút.");
    },
  });
}
