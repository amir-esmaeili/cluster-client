# Multi-stage build for production
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling

# Copy source code
COPY src/ src/

# Build wheel
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels .

# Runtime stage
FROM python:3.12-slim

# Create non-root user
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

WORKDIR /app

# Copy wheels from builder
COPY --from=builder /build/wheels /tmp/wheels
COPY --from=builder /build/pyproject.toml .

# Install the application
RUN pip install --no-cache-dir /tmp/wheels/*.whl && \
    rm -rf /tmp/wheels

# Switch to non-root user
USER appuser

# Set Python to run in unbuffered mode for logging
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "cluster_client.cli"]
CMD ["--help"]
