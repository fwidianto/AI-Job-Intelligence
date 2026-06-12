# =============================================================================
# AI Job Intelligence Platform - Docker Container
# =============================================================================
# Optimized for headless operation and scheduled runs

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# =============================================================================
# METADATA
# =============================================================================
LABEL org.opencontainers.image.title="AI Job Intelligence Platform"
LABEL org.opencontainers.image.description="Automated job opportunity discovery and tracking"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="Job Intelligence Platform"

# =============================================================================
# DEPENDENCIES
# =============================================================================
# Install build dependencies for cryptography (needed by google-auth)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
# APPLICATION FILES
# =============================================================================
COPY . .

# =============================================================================
# RUNTIME SETUP
# =============================================================================
# Create logs directory
RUN mkdir -p /app/logs

# Create credentials directory
RUN mkdir -p /app/credentials

# Set Python to not generate .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Set Python to unbuffered output
ENV PYTHONUNBUFFERED=1

# =============================================================================
# HEALTH CHECK
# =============================================================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# =============================================================================
# DEFAULT COMMAND
# =============================================================================
# Run with test-scorer by default to verify setup
CMD ["python", "src/main.py", "--test-scorer"]

# =============================================================================
# ALTERNATIVE COMMANDS (use docker run)
# =============================================================================
# docker run job-intelligence python src/main.py --help
# docker run job-intelligence python src/main.py --test-collectors
# docker run job-intelligence python src/main.py  # Full run