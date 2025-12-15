# Dockerfile Workaround
# Verwenden Sie das Python-Basis-Image direkt für Ihre aarch64 Architektur
FROM ghcr.io/home-assistant/aarch64-python-base:latest

WORKDIR /app

# Installiere pyserial mithilfe des nun vorhandenen python3
RUN python3 -m pip install --no-cache-dir pyserial==3.5

COPY run.py /app/run.py

CMD ["python3", "/app/run.py"]
