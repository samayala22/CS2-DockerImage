FROM registry.gitlab.steamos.cloud/steamrt/sniper/sdk

ARG UV_VERSION=0.12.12

RUN useradd -m -s /bin/bash -u 1000 steam

USER steam
WORKDIR /home/steam

# Project files (pyproject.toml, uv.lock, scripts) go in first so uv can sync.
COPY src /src

# uv manages both the Python runtime and the project deps, so nothing needs apt.
RUN NO_MODIFY_PATH=1 curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh | sh \
    && ~/.local/bin/uv sync --frozen \
    && rm -rf ~/.cache/uv

# UV_PROJECT points uv at the project regardless of the working directory, so
# the commands stay short. --no-sync keeps every invocation offline; docker runs
# the healthcheck with the same WORKDIR, so both commands work unchanged.
ENV PATH="/home/steam/.local/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT=/src

HEALTHCHECK --interval=60s --timeout=5s --retries=3 --start-period=3m \
    CMD ["uv", "run", "--no-sync", "/src/healthcheck.py"]

ENTRYPOINT ["uv", "run", "--no-sync", "/src/entrypoint.py"]
