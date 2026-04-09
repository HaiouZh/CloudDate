FROM python:3.12-slim

LABEL maintainer="CloudDate"
LABEL description="Lightweight cloud server resource monitor"

WORKDIR /app

# Install dependencies first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server/ ./server/
COPY web/ ./web/

# Default environment variables
ENV PORT=5001
ENV HOST=0.0.0.0
ENV TOKEN=""
ENV RING_BUFFER_SIZE=3600
ENV SLEEP_DELAY=30
ENV HOST_PROC=/host/proc
ENV HOST_SYS=/host/sys
ENV HOST_ETC=/host/etc
ENV PROCESS_LIMIT=50

EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/api/config')" || exit 1

CMD ["python", "-m", "server.main"]
