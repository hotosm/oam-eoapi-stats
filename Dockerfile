FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

LABEL org.opencontainers.image.source="https://github.com/hotosm/oam-eoapi-stats/"

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT="/usr/local/"

WORKDIR /code

# Dependencies first, so source changes don't invalidate this layer.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY pyproject.toml uv.lock README.md LICENSE /code/
COPY src /code/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

RUN useradd --system --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "oam_eoapi_stats.main:app", "--host", "0.0.0.0", "--port", "8000"]
