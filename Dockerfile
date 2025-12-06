# Base image
ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

# Set working directory
WORKDIR /app

# Install Python and venv
RUN apk add --no-cache python3 py3-pip python3-venv

# Create virtual environment
RUN python3 -m venv /opt/venv

# Activate venv and install pyserial
RUN /bin/sh -c "source /opt/venv/bin/activate && pip install --no-cache-dir pyserial"

# Copy add-on script
COPY run.py /run.py

# Set environment variable for Python
ENV PATH="/opt/venv/bin:$PATH"

# Default command
CMD [ "python3", "/run.py" ]
