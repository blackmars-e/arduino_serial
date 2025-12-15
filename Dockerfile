ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Python ist bereits im Base-Image enthalten
# pip ebenfalls – KEIN apk add python3 nötig

# pyserial installieren – HA-konform (PEP 668!)
RUN pip install --no-cache-dir --break-system-packages pyserial==3.5

COPY run.py /app/run.py

CMD ["python3", "/app/run.py"]

