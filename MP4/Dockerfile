# ======================
# Universal Media Resolver v2.1
# Works Anywhere - Production Ready
# ======================

# Stage 1: Builder
FROM python:3.11-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev \
    make \
    git \
    curl

WORKDIR /app

# Copy requirements first (better layer caching)
COPY backend/requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ======================
# Stage 2: Runtime
# ======================
FROM python:3.11-alpine

# Metadata
LABEL org.opencontainers.image.title="Universal Media Resolver"
LABEL org.opencontainers.image.description="Docker-native media resolver for 1000+ sites"
LABEL org.opencontainers.image.version="2.1.0"
LABEL org.opencontainers.image.licenses="MIT"

# Environment variables
ENV HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=2 \
    LOG_LEVEL=info \
    JWT_SECRET=change-in-production \
    TOKEN_EXPIRE_MINUTES=30 \
    CORS_ORIGINS="*" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/bin:${PATH}"

# Install ALL runtime dependencies
RUN apk add --no-cache \
    ffmpeg \
    curl \
    git \
    bash \
    ca-certificates \
    tzdata \
    openssl \
    su-exec \
    jq \
    wget \
    && update-ca-certificates \
    && rm -rf /var/cache/apk/*

# Create non-root user with fixed UID/GID
RUN addgroup -g 1000 -S appgroup \
    && adduser -u 1000 -S appuser -G appgroup -h /app \
    && mkdir -p /app/.cache /app/.config \
    && chown -R appuser:appgroup /app/.cache /app/.config

WORKDIR /app

# Copy wheels and install Python dependencies
COPY --from=builder --chown=appuser:appgroup /wheels /wheels
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels \
    && rm -rf /root/.cache/pip

# Copy application code
COPY backend/ /app/
COPY docker-entrypoint.sh /app/

# Make entrypoint executable
RUN chmod +x /app/docker-entrypoint.sh

# Create directories with correct permissions
RUN mkdir -p /app/data /app/logs /app/cache /app/temp \
    && chown -R appuser:appgroup /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD sh -c "curl -f http://localhost:${PORT}/health || exit 1"

EXPOSE ${PORT}

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["start-server"]