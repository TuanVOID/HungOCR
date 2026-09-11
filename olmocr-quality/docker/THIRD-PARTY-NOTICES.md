# Third-party components and reproducibility pins

This portable package combines third-party software and model weights. It does
not change their licenses. Review the linked upstream terms before redistribution
or production use.

## Container bases and Python packages

- `vllm/vllm-openai@sha256:2286e8533ca8b6bc777594bae30524f1426ba46ca21797524e06df6a94b06635`
  with vLLM 0.28.0 — Apache-2.0.
- `node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5`.
- `olmocr==0.4.27` — Apache-2.0.
- `pypdf==6.17.0` — BSD-3-Clause.
- `torch==2.13.0+cu130` — package metadata lists Apache-2.0 and bundled
  third-party license expressions.
- `nvidia-nccl-cu13==2.29.7` — NVIDIA proprietary license terms. This exact
  version is required by the pinned torch build; do not upgrade it independently.

The complete installed environment is inside `olmocr-image.tar`; its package
metadata and license files remain available in the image. The Dockerfile and
minimal application source needed to reproduce the custom layer are in `source/`.

## Model

- Model: `allenai/olmOCR-2-7B-1025-FP8`.
- Snapshot: `40bd7202494b8264ee17ada08b401b5aab7a9ce1`.
- Declared license: Apache-2.0.
- Base model declared by the model card: `Qwen/Qwen2.5-VL-7B-Instruct`.

The copied model directory includes its original `README.md` model card. Keep it
with the weights. The package manifest hashes every shipped model file.

## Local adapter source

The project-level `LICENSE` copied into `source/LICENSE` applies to the local
HungOCR repository source. The legal-preserve adapter is a local wrapper around
olmOCR; it does not modify the installed olmOCR package.
