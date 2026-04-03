FROM python:3.10-slim

# Install system dependencies, specifically default-jre (Java 17) for opendataloader-pdf
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port and start command
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
