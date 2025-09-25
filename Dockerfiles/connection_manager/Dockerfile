FROM python:3.12-bookworm as base

WORKDIR /app/src

RUN pip install uv

# ---- Builder Stage ----
FROM base as builder

COPY pyproject.toml uv.lock ./
ENV UV_PROJECT_ENVIRONMENT=/usr/local
RUN uv sync --no-dev --locked

# ---- Final Stage ----
FROM base as prod
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY ./connection_manager /app/src/connection_manager

ENV MANAGER_HOST=0.0.0.0
ENV MANAGER_PORT=8000

EXPOSE $MANAGER_PORT

CMD uvicorn --host $MANAGER_HOST --port $MANAGER_PORT --log-level info connection_manager:app

