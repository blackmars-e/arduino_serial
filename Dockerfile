ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Python + pip
RUN apk add --no-cache python3 py3-pip

# pyserial installieren (PEP 668 korrekt umgehen)
RUN pip3 install --no-cache-dir --break-system-packages pyserial==3.5

# Script kopieren
COPY run.py /app/run.py

# Start
CMD ["python3", "/app/run.py"]
