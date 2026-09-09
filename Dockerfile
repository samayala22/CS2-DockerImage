FROM registry.gitlab.steamos.cloud/steamrt/sniper/sdk

ARG UV_VERSION=0.12.12

RUN NO_MODIFY_PATH=1 curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh | sh \
    && install -m 0755 /root/.local/bin/uv /usr/local/bin/uv \
    && rm -rf /root/.local /root/.cache/uv

RUN useradd -m -s /bin/bash -u 1000 steam

USER steam
WORKDIR /src

# Project files (pyproject.toml, uv.lock, scripts) go in first so uv can sync.
COPY src /src

RUN /usr/local/bin/uv sync --frozen \
    && rm -rf ~/.cache/uv

ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=60s --timeout=5s --retries=3 --start-period=3m \
    CMD ["uv", "run", "--no-sync", "healthcheck.py"]

ENTRYPOINT ["uv", "run", "--no-sync", "entrypoint.py"]