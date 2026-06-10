from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT_DIR = Path(__file__).resolve().parent
APP_FILE = ROOT_DIR / "app.py"
LOCAL_VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"

# Load environment variables from .env
def load_env():
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        val_str = val.strip()
                        if len(val_str) >= 2 and val_str[0] == val_str[-1] and val_str[0] in ('"', "'"):
                            val_str = val_str[1:-1]
                        os.environ[key.strip()] = val_str

load_env()

PORT = os.getenv("PORT", "5000")
DEFAULT_BASE_URL = os.getenv("OCR_BASE_URL", f"http://127.0.0.1:{PORT}")
DEFAULT_HEALTH_URL = os.getenv("OCR_HEALTH_URL", f"{DEFAULT_BASE_URL}/health")
STARTUP_TIMEOUT_SECONDS = int(os.getenv("OCR_STARTUP_TIMEOUT_SECONDS", "120"))


def resolve_python_executable() -> str:
    if LOCAL_VENV_PYTHON.exists():
        return str(LOCAL_VENV_PYTHON)
    return sys.executable


def wait_until_ready(health_url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error = None

    while time.time() < deadline:
        try:
            with urlopen(health_url, timeout=3) as response:
                if 200 <= getattr(response, "status", 200) < 500:
                    return
        except URLError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc

        time.sleep(1)

    raise RuntimeError(
        f"Backend did not become ready within {timeout_seconds} seconds."
        + (f" Last error: {last_error}" if last_error else "")
    )


def start_backend() -> subprocess.Popen:
    return subprocess.Popen(
        [resolve_python_executable(), str(APP_FILE)],
        cwd=str(ROOT_DIR),
    )


def run_full() -> int:
    process = start_backend()
    try:
        wait_until_ready(DEFAULT_HEALTH_URL, STARTUP_TIMEOUT_SECONDS)
        webbrowser.open(DEFAULT_BASE_URL)
        print(f"Backend is ready. Opened UI at {DEFAULT_BASE_URL}")
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        return 130
    except Exception as exc:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        raise SystemExit(str(exc))


def run_be() -> int:
    return subprocess.call([resolve_python_executable(), str(APP_FILE)], cwd=str(ROOT_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR launcher for the PaddleOCR Flask app.")
    parser.add_argument(
        "mode",
        choices=("full", "be"),
        help="Use 'full' to start backend and open the UI, or 'be' to start backend only.",
    )
    args = parser.parse_args()

    if args.mode == "full":
        return run_full()
    return run_be()


if __name__ == "__main__":
    raise SystemExit(main())
