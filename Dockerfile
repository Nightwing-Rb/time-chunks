FROM python:3.10-slim

# Install system dependencies: Java 17 (required by opendataloader-pdf)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Verify Java is available at build time
RUN java -version && echo "Java installed successfully"

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Render injects $PORT automatically; fall back to 8000 for local/dev
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
