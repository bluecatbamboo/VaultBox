# Multi-stage build for SMTP Email Server
FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies including Redis
RUN apt-get update && apt-get install -y \
    openssl \
    curl \
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r smtpuser && useradd -r -g smtpuser smtpuser

# Set working directory
WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /root/.local /home/smtpuser/.local

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p data logs && \
    chown -R smtpuser:smtpuser /app && \
    chmod +x run.sh

# Make entrypoint script executable
RUN chmod +x /app/docker/docker-entrypoint.sh

# Add user's local bin to PATH
ENV PATH="/home/smtpuser/.local/bin:$PATH"

# Environment variables with defaults
# Note: Sensitive variables (SECRET_KEY, EMAIL_ENCRYPTION_KEY, EMAIL_UI_USERS) 
# have no defaults for security - they must be provided at runtime
ENV ENABLE_SWAGGER="true" \
    ENABLE_UI="true" \
    COOKIE_SECURE="false" \
    ACCESS_TOKEN_EXPIRE_MINUTES="30" \
    LOG_LEVEL="INFO" \
    SMTP_PORT="587" \
    WEB_PORT="8001" \
    SMTP_HOST="0.0.0.0" \
    WEB_HOST="0.0.0.0" \
    REDIS_HOST="localhost" \
    REDIS_PORT="6379" \
    REDIS_URL="redis://localhost:6379" \
    REDIS_QUEUE="smtp_emails" \
    REDIS_PUBSUB_PREFIX="email_notify:" \
    DATABASE_URL="sqlite:///./data/emails.db" \
    ALGORITHM="HS256"

# Sensitive environment variables (no defaults for security):
# SECRET_KEY - JWT signing key (REQUIRED)
# EMAIL_ENCRYPTION_KEY - Email content encryption key (REQUIRED)  
# EMAIL_UI_USERS - User credentials (REQUIRED)

# Expose ports (configurable via environment)
EXPOSE $SMTP_PORT $WEB_PORT

# Add volume for persistent data
VOLUME ["/app/data", "/app/logs"]

# Switch to non-root user
USER smtpuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${WEB_PORT:-8001}/api/me || exit 1

# Use entrypoint script to ensure DB is created only if missing
ENTRYPOINT ["/app/docker/docker-entrypoint.sh"]

# Default command
CMD ["start"]
