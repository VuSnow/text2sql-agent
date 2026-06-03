FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and install package
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

# Copy data directory (docs, examples, prompts for RAG seeding)
COPY data/ ./data/

# Non-root user for security
RUN useradd --create-home appuser && \
    chown -R appuser:appuser /app/data
USER appuser

# Expose default agent port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8080/health'); r.raise_for_status()" || exit 1

# Run the agent server
CMD ["uvicorn", "text2sql_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
