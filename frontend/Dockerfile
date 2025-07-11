# frontend/Dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY frontend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY frontend/ .

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "streamlit_app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]

# ---

# scripts/Dockerfile.init
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy initialization scripts and backend code
COPY scripts/ ./scripts/
COPY backend/ ./backend/

# Create directory for ChromaDB data
RUN mkdir -p /app/chromadb_data

# Make scripts executable
RUN chmod +x /app/scripts/*.py

# Default command
CMD ["echo", "Database initialization container ready"]
