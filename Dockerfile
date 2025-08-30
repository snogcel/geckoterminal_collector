# Multi-stage build for GeckoTerminal Data Collector
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION=0.1.0
ARG VCS_REF

# Add metadata labels
LABEL maintainer="GeckoTerminal Data Collector Team" \
      org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="gecko-terminal-collector" \
      org.label-schema.description="Cryptocurrency data collection system for GeckoTerminal API" \
      org.label-schema.version=$VERSION \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.schema-version="1.0"

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

# Production stage
FROM python:3.11-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r gecko && useradd -r -g gecko gecko

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app /app

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs /app/backups && \
    chown -R gecko:gecko /app

# Switch to non-root user
USER gecko

# Set environment variables
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    GECKO_CONFIG_FILE=/app/config.yaml \
    GECKO_DB_URL=sqlite:///app/data/gecko_data.db \
    GECKO_LOG_LEVEL=INFO

# Expose health check port (if health endpoints are implemented)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -m gecko_terminal_collector.cli health-check --json || exit 1

# Default command
CMD ["python", "-m", "gecko_terminal_collector.cli", "start", "--daemon"]