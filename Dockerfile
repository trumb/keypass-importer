# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

# Runtime stage
FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/keypass-importer /usr/local/bin/keypass-importer

# Non-root user
RUN useradd --create-home appuser
USER appuser

ENTRYPOINT ["keypass-importer"]
