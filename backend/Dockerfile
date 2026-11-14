FROM python:3.12-slim

# Tesseract with Finnish and Swedish for OCR on raster drawings; DejaVu so rendered
# pages draw accented letters (é, ä, ł...) instead of boxes.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-fin tesseract-ocr-swe \
    fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# OCR on a GPU host (#119): `--build-arg ONNX_GPU=1` swaps onnxruntime for its CUDA 12
# build, which the OCR service uses (app/ocr_server.py). 1.26.0 is the last CUDA 12
# release (1.28+ need CUDA 13, which no longer runs on a Tesla V100), and cuDNN 9.10.2 is
# the one PyTorch's V100 build ships. Empty (the default) keeps the CPU build, so
# `make up-local` and Aiven are unchanged.
ARG ONNX_GPU=
RUN if [ -n "$ONNX_GPU" ]; then \
      uv pip uninstall --python /app/.venv/bin/python onnxruntime \
      && uv pip install --python /app/.venv/bin/python \
        "onnxruntime-gpu[cuda,cudnn]==1.26.0" "nvidia-cudnn-cu12==9.10.2.21" \
      && rm -rf /root/.cache; \
    fi
COPY app ./app

RUN useradd --create-home app && mkdir -p /data && chown app /data
USER app
EXPOSE 8000
# The worker uses the same image: `python -m app.worker` (see docker-compose.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
