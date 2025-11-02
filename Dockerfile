# Multi-stage Dockerfile for Cloud Run deployment with C++ support

# Build stage
FROM python:3.11-slim as build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Build C++ extension
COPY cppmatch.cpp setup.py ./
RUN python setup.py build_ext --inplace

# Copy application files
COPY . .

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Copy built application from build stage
COPY --from=build /app /app

# Install Python dependencies in runtime
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV PORT=8080
ENV TERMS_PATH=data/mrconso_sample.txt

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips=*"]
