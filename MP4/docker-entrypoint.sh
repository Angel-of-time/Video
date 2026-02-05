#!/bin/sh
# docker-entrypoint.sh v2.1 - Production-hardened
set -euo pipefail

# ======================
# Environment Detection
# ======================

echo "🔍 Universal Media Resolver v2.1"
echo "================================"

# Function: Safe numeric comparison using awk
is_greater_than() {
    awk -v n1="$1" -v n2="$2" 'BEGIN {print (n1 > n2) ? "true" : "false"}'
}

# Function: Detect memory limit (Cgroup v1 & v2 compatible)
detect_memory_limit() {
    local limit_bytes="0"
    
    # Try Cgroup v2 first
    if [ -f /sys/fs/cgroup/memory.max ]; then
        limit_bytes=$(cat /sys/fs/cgroup/memory.max)
        if [ "$limit_bytes" = "max" ]; then
            echo "0"
            return
        fi
    # Try Cgroup v1
    elif [ -f /sys/fs/cgroup/memory/memory.limit_in_bytes ]; then
        limit_bytes=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes)
    fi
    
    # Use awk for safe comparison with 1TB
    if [ "$(is_greater_than "$limit_bytes" "1099511627776")" = "true" ]; then
        echo "0"
    else
        echo "${limit_bytes}"
    fi
}

# ======================
# Configuration
# ======================

# Detect memory and auto-configure workers
MEM_BYTES=$(detect_memory_limit)
if [ "$MEM_BYTES" = "0" ]; then
    echo "📊 Memory: Unlimited/Unknown"
    if command -v nproc >/dev/null 2>&1; then
        CPU_CORES=$(nproc)
        export WORKERS=$((CPU_CORES > 4 ? 4 : CPU_CORES))
        echo "⚡ CPU cores: ${CPU_CORES}, workers: ${WORKERS}"
    else
        export WORKERS=2
        echo "⚡ Default workers: ${WORKERS}"
    fi
else
    MEM_MB=$((MEM_BYTES / 1024 / 1024))
    echo "📊 Memory limit: ${MEM_MB}MB"
    
    # Auto-scale workers based on memory
    if [ "$(is_greater_than "$MEM_MB" "1024")" = "true" ]; then
        export WORKERS=4
    elif [ "$(is_greater_than "$MEM_MB" "512")" = "true" ]; then
        export WORKERS=2
    else
        export WORKERS=1
    fi
    echo "👥 Setting workers: ${WORKERS}"
fi

# Check for FFmpeg
if command -v ffmpeg >/dev/null 2>&1 && ffmpeg -version >/dev/null 2>&1; then
    echo "✅ FFmpeg available"
    export HAS_FFMPEG="true"
else
    echo "⚠️  FFmpeg not available - conversion disabled"
    export HAS_FFMPEG="false"
fi

# Generate JWT secret if not provided
if [ "${JWT_SECRET:-}" = "change-in-production" ] || [ -z "${JWT_SECRET:-}" ]; then
    if [ -f /app/data/jwt_secret.txt ]; then
        export JWT_SECRET=$(cat /app/data/jwt_secret.txt)
        echo "🔑 Using existing JWT secret"
    else
        # Generate secure random secret with multiple fallbacks
        export JWT_SECRET=$(openssl rand -hex 32 2>/dev/null || \
                           date +%s%N | sha256sum | base64 | head -c 32 || \
                           echo "fallback-secret-$(date +%s)")
        mkdir -p /app/data
        echo "$JWT_SECRET" > /app/data/jwt_secret.txt
        chmod 600 /app/data/jwt_secret.txt
        echo "🔑 Generated new JWT secret"
    fi
fi

# ======================
# Permission Fixes (Root Phase)
# ======================

echo "🔒 Setting up permissions..."

# We are root here - fix volume permissions before dropping privileges
if [ -d /app ]; then
    # Ensure all required directories exist
    mkdir -p /app/data /app/logs /app/cache /app/temp
    
    # Check ownership before chown to save startup time
    if [ -d /app/data ] && [ "$(stat -c '%u:%g' /app/data 2>/dev/null || echo '0:0')" != "1000:1000" ]; then
        echo "🔧 Fixing volume permissions (this may take a moment on first run)..."
        chown -R 1000:1000 /app/data /app/logs /app/cache /app/temp 2>/dev/null || true
        find /app/data /app/logs /app/cache /app/temp -type d -exec chmod 755 {} \; 2>/dev/null || true
        find /app/data /app/logs /app/cache /app/temp -type f -exec chmod 644 {} \; 2>/dev/null || true
    else
        echo "🔧 Volume permissions already correct."
    fi
fi

# ======================
# Privilege Drop & Execution
# ======================

CMD="${1:-}"
shift || true

case "$CMD" in
    "start-server")
        echo "🚀 Starting Media Resolver..."
        echo "🌐 Listening on: ${HOST}:${PORT}"
        echo "📝 Log level: ${LOG_LEVEL}"
        echo "👤 Will run as: appuser:appgroup (UID 1000:1000)"
        echo "================================"
        
        # Drop privileges and execute using su-exec
        exec su-exec appuser:appgroup \
            uvicorn main:app \
            --host "$HOST" \
            --port "$PORT" \
            --workers "$WORKERS" \
            --log-level "${LOG_LEVEL}" \
            --no-access-log \
            --proxy-headers
        ;;
    
    "shell"|"bash")
        echo "🐚 Starting shell as appuser..."
        exec su-exec appuser:appgroup /bin/bash
        ;;
    
    "sh")
        echo "🐚 Starting shell as appuser..."
        exec su-exec appuser:appgroup /bin/sh
        ;;
    
    "python")
        exec su-exec appuser:appgroup python "$@"
        ;;
    
    "pip")
        exec su-exec appuser:appgroup pip "$@"
        ;;
    
    "health-check")
        exec su-exec appuser:appgroup \
            sh -c 'curl -f "http://localhost:${PORT}/health" 2>/dev/null && echo "✅ Healthy" || (echo "❌ Unhealthy"; exit 1)'
        ;;
    
    *)
        echo "⚡ Executing: $CMD $@"
        exec su-exec appuser:appgroup "$CMD" "$@"
        ;;
esac