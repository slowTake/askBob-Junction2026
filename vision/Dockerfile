FROM python:3.12-slim

# The floor-plan model service (D-022). CPU-only PyTorch comes from the index in
# pyproject.toml. CubiCasa5k's code and weights are CC BY-NC 4.0: fetched here at
# build time, never committed, for non-commercial use only.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" CUBICASA_DIR=/opt/cubicasa VISION_WEIGHTS=/opt/weights/cubicasa.pt

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Model code at a pinned commit. The sed fixes one call for current SciPy, where
# stats.mode(...).mode is a scalar instead of an array.
ARG CUBICASA_COMMIT=c34440266665a11f4484eb06cd2e4b7d72ad76c1
RUN git clone --quiet https://github.com/CubiCasa/CubiCasa5k.git /opt/cubicasa \
 && git -C /opt/cubicasa checkout --quiet "$CUBICASA_COMMIT" \
 && rm -rf /opt/cubicasa/.git \
 && sed -i -E 's/stats\.mode\(([^)]*)\)\.mode\[0\]/np.atleast_1d(stats.mode(\1).mode)[0]/g' \
      /opt/cubicasa/floortrans/post_prosessing.py

# Pretrained weights from the link in CubiCasa5k's README (Google Drive). Only the
# model state is kept, which drops the optimiser state from the 209 MB checkpoint.
ARG CUBICASA_WEIGHTS_ID=1gRB7ez1e4H7a9Y09lLqRuna0luZO5VRK
RUN mkdir -p /opt/weights \
 && uvx --from gdown==5.2.0 gdown --quiet "$CUBICASA_WEIGHTS_ID" -O /tmp/ckpt.pkl \
 && python -c "import torch; c = torch.load('/tmp/ckpt.pkl', map_location='cpu', weights_only=False); torch.save(c['model_state'], '/opt/weights/cubicasa.pt')" \
 && rm /tmp/ckpt.pkl && rm -rf /root/.cache

COPY app ./app
RUN useradd --create-home app
USER app
EXPOSE 8001
CMD ["uvicorn", "--factory", "app.main:serve", "--host", "0.0.0.0", "--port", "8001"]
