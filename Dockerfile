ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

WORKDIR /app

# Optional: venv erstellen
RUN python3 -m venv /opt/venv

# pip upgraden und pyserial installieren
RUN /opt/venv/bin/python3 -m pip install --upgrade pip setuptools wheel
RUN /opt/venv/bin/python3 -m pip install --no-cache-dir pyserial==3.5

# Copy script
COPY run.py /app/run.py

# PATH anpassen, damit venv benutzt wird
ENV PATH="/opt/venv/bin:$PATH"

# CMD nutzt automatisch die venv-Python
CMD ["python3", "/app/run.py"]
