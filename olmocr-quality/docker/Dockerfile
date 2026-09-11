FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS node
FROM vllm/vllm-openai@sha256:2286e8533ca8b6bc777594bae30524f1426ba46ca21797524e06df6a94b06635
USER root
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
RUN python3 -m pip install --no-cache-dir olmocr==0.4.27 pypdf==6.17.0 nvidia-nccl-cu13==2.29.7 && python3 -m pip check
WORKDIR /app
COPY legal_pipeline.py ocr.sh serve.sh ./
COPY ui ./ui
ENV OLMOCR_CONTAINER=1 OLMOCR_JOBS_ROOT=/data/jobs OLMOCR_MODEL_PATH=/models/olmocr \
    XDG_CACHE_HOME=/cache HF_HOME=/cache/huggingface HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    VLLM_USE_V2_MODEL_RUNNER=0 PYTHONUNBUFFERED=1
EXPOSE 8010
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 CMD node -e "fetch('http://127.0.0.1:8010/api/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
ENTRYPOINT ["node", "/app/ui/server.mjs"]
