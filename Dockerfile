ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-python-base:latest
FROM ${BUILD_FROM}

WORKDIR /app

# pyserial installieren
RUN python3 -m pip install --no-cache-dir pyserial==3.5

COPY run.py /app/run.py

CMD ["python3", "/app/run.py"]
