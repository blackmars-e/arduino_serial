ARG BUILD_FROM
FROM $BUILD_FROM

# Installation von Python und sed zum Fixen der Zeilenenden
RUN apk add --no-cache python3 py3-pip sed

WORKDIR /app

# Pyserial installieren
RUN pip3 install --no-cache-dir --break-system-packages pyserial

# Dateien kopieren
COPY run.py .
COPY run.sh .

# KRITISCH: Erzwinge Linux-Zeilenenden und mache das Script ausführbar
RUN sed -i 's/\r$//' /app/run.sh && \
    sed -i 's/\r$//' /app/run.py && \
    chmod +x /app/run.sh

# Starte über das Shell-Script
ENTRYPOINT ["/usr/bin/env"]
CMD ["sh", "/app/run.sh"]
