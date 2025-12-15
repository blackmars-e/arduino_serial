############################################################
# Home Assistant Add-on: Arduino Serial Controller
# Plattform: aarch64 (Raspberry Pi 3 64-bit)
# Home Assistant OS Base Image: ghcr.io/home-assistant/aarch64-base:latest
############################################################

# Base image
ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

# Arbeitsverzeichnis
WORKDIR /app

# pyserial installieren über Python
RUN python -m ensurepip && \
    python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir pyserial==3.5

# Addon Script kopieren
COPY run.py /app/run.py

# Standardbefehl
CMD ["python", "/app/run.py"]
