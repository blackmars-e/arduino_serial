FROM ghcr.io/home-assistant/aarch64-base:latest

WORKDIR /app

# Install Python system packages
RUN apk add --no-cache python3 py3-pip

# Create virtual environment
RUN python3 -m venv /opt/venv

# Activate venv and install pyserial
RUN /opt/venv/bin/pip install --upgrade pip pyserial

# Copy your script
COPY run.py /app/run.py

# Use the virtual environment when running
ENTRYPOINT ["/opt/venv/bin/python", "/app/run.py"]
