ARG BUILD_FROM
FROM $BUILD_FROM

# Basis-Pakete installieren
RUN apk add --no-cache \
    python3 \
    py3-pip \
    sed

WORKDIR /app

# Pyserial installieren (break-system-packages ist nötig in neuen Alpine-Versionen)
RUN pip3 install --no-cache-dir --break-system-packages pyserial

# Dateien kopieren
COPY run.py .
COPY run.sh .

# Zeilenenden fixen (wichtig für Windows-Nutzer) & Rechte setzen
RUN sed -i 's/\r$//' run.sh && chmod a+x run.sh

# Start-Kommando
CMD [ "/app/run.sh" ]
