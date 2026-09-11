# olmOCR — Quality First

For the portable, authenticated Docker deployment, read
[`docker/README-VI.md`](docker/README-VI.md). The instructions below describe the
older local WSL workflow and remain available for development; do not run both
model servers concurrently on a 16 GB GPU.

Windows launchers use the existing WSL2 distribution `Ubuntu`. Python and CUDA
packages are isolated in `/home/imdevil/olmocr-quality/.venv`; model weights live
in the Linux Hugging Face cache. The Windows NVIDIA driver is shared with WSL;
do not install a Linux display driver inside Ubuntu.

## Start and stop

## Web interface

Run `./start-ui.ps1`, then open http://localhost:8010. Start the OCR model
with `./start.ps1` if the interface reports that the OCR server is unavailable.
The interface accepts one PDF at a time (up to 100 MB), or the supplied sample.
It shows the source PDF beside the raw OCR Markdown, keeps processing history,
and provides Markdown/JSONL downloads and the pipeline log. Each run receives
a separate directory in `ui-workspace/`, so uploading the same PDF reruns OCR.
Files and job metadata stay on disk until manually removed. The interface binds
to localhost only. Keep the UI process running while a document is processing.

The web server requires Node.js and uses only its built-in modules. It calls the
existing WSL `ocr.sh`; it does not need another model or Python environment.
Use `./stop-ui.ps1` to stop the UI when no OCR job is active.

## Model server

Run `./start.ps1` in PowerShell. It opens a hidden WSL keep-alive process because
WSL otherwise shuts down this distro when no Windows-side WSL process remains.
The first startup includes model loading and kernel compilation. Wait for
`http://localhost:8000/health` to return HTTP 200.
The OpenAI-compatible endpoint is `http://localhost:8000/v1`, model name `olmocr`.

Logs: `wsl -d Ubuntu -- tail -f /home/imdevil/olmocr-quality/vllm.log`

Stop: `./stop.ps1`. The service is manually started; no boot-time autostart is
installed. At utilization 0.86, about 14 GB of the 16 GB GPU must be available
at startup. Other GPU workloads may need to be stopped first.

## Convert

```powershell
./run-ocr.ps1
./run-ocr.ps1 -InputPdf 'D:\OCR\input\*.pdf' -Workspace 'D:\OCR\workspace'
```

The first command processes `docling/docs/test_OCR.pdf`. This file contains four
pages. The second command matches the example input folder requested by the user.
The toolkit writes Markdown plus JSONL (one JSON document record per line).
Use a new workspace to rerun a previously completed document; existing workspaces
track completed work for resume.

## Exact profile

- Model: `allenai/olmOCR-2-7B-1025-FP8`
- Served name: `olmocr`; context 16384; GPU utilization 0.86; max sequences 2
- Tensor parallel size 1; KV-cache dtype left at vLLM default
- Per request: one image, zero videos
- Vision processor `max_pixels=589824`: limits the processed image pixel budget.
  This affects image processing at inference as well as startup profiling.
  The toolkit renders at 1288 px, but the model processor can downsize that image.
- Image longest side 1288 px; workers 1; concurrent requests 2
- `apply_filter` OFF; `guided_decoding` OFF (both flags omitted)
- Profile `legal-preserve-v2`: official full-page OCR plus a separate recognition
  pass on the top 24% of the first page, with a document-identification prompt.
  Recovered authority, national heading/motto, document number and issue date
  are prepended to the first page before Markdown/JSONL export.
- Official retry logic (8 page attempts in installed version) is unchanged.

The vLLM V2 model runner is disabled because it requires CUDA UVA, which WSL2
does not expose. This selects vLLM's compatible runner without changing model,
context, memory, concurrency, or OCR generation settings.

`legal_pipeline.py` wraps the page/query callbacks for this invocation only;
the installed toolkit is not edited. The adapter checks olmocr 0.4.27 to make
upgrades explicit. Both the UI and CLI use this adapter via `ocr.sh`.
Identification fields are transcribed only when visible, never filled from a
template. OCR can still misread small or damaged text: verify identifiers against
the PDF. Previous outputs are unchanged; rerun using the UI or a fresh workspace.
The crop pass uses the same model, request semaphore and official retry mechanism.
Logs count this extra recognition pass in their completed-page metrics; it is not
an additional source PDF page. Headers outside the opening crop and documents
containing multiple independent acts may require separate handling.
`apply_filter` still controls toolkit document filtering. This does not integrate
olmOCR into Docling's dropdown.

Sources: [olmOCR toolkit](https://github.com/allenai/olmocr),
[vLLM installation](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).

## On-demand model lifecycle

Keep `start-ui.ps1` running. The UI job service now loads the WSL model automatically
when a valid OCR job arrives and stops `olmocr-vllm.service` after 300 seconds idle.
The timer checks once per second; service shutdown can take a few additional seconds.
An entire UI job reserves the model, including gaps between pages. Direct vLLM
running/waiting requests and completed-request counters also extend the idle timer.
Health polling, viewing history, and downloading results do not extend it.
Unknown/unavailable metrics never authorize stopping a running model.

`GET /api/health` reports `ready` for accepting jobs; `model_ready` and `model_state`
report physical model readiness. An unloaded model still accepts jobs. Cold loading
is included in the running job and may take a few minutes; failures appear on that
job and can be retried. No model files or OCR results are deleted on unload.
The idle manager only runs while the UI service runs. For an explicit shutdown use
`stop.ps1`; `stop-ui.ps1` alone stops only the UI and its idle manager.

Verification: `node --test olmocr-quality/ui/model-lifecycle.test.mjs` from repo root.
