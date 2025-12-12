FROM python:3.10.18-slim-bookworm

# Set the working directory for the application.
WORKDIR /app

# Install necessary system dependencies for Google Cloud SDK.
# Use --no-install-recommends to keep the image smaller.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    gnupg \
    curl \
    tar && \
    rm -rf /var/lib/apt/lists/*

# Install Google Cloud CLI
# Use a specific version of gcloud CLI for reproducibility, if possible.
# Here we'll install the latest stable version.
# ENV GCLOUD_CLI_VERSION="479.0.0"  # Example: use a specific version
RUN curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-479.0.0-linux-x86_64.tar.gz && \
    tar -xf google-cloud-cli-479.0.0-linux-x86_64.tar.gz && \
    ./google-cloud-sdk/install.sh --usage-reporting=false --path-update=true --rc-path=/etc/profile.d/gcloud.sh --quiet && \
    rm google-cloud-cli-479.0.0-linux-x86_64.tar.gz

# Add gcloud CLI to the PATH
ENV PATH="/google-cloud-sdk/bin:${PATH}"

# Copy the requirements file first to leverage Docker's layer caching.
# Use the WORKDIR /app, so the file is copied into /app.
COPY requirements.txt .

# Install Python dependencies.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt



# Copy the application code.
# Use the WORKDIR /app, so the code is copied into /app.
COPY gke-mcp ./gke-mcp

# Expose the default port if you plan to use HTTP/SSE transport.
# This is where your FastAPI/Uvicorn server (managed by FastMCP) will listen.
EXPOSE 8001
# Set the entrypoint for the container.
ENTRYPOINT ["python3", "-m", "gke-mcp", "--transport", "sse"]
