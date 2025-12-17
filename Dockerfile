ARG BUILD_FROM
FROM $BUILD_FROM

# Installiere Pakete
RUN apk add --no-cache python3 py3-pip

WORKDIR /app

# Venv erstellen
RUN python3 -m venv /opt/venv

# Requirements installieren
RUN /opt/venv/bin/pip install --upgrade pip pyserial

# Kopiere Dateien
COPY run.py /app/run.py
COPY run.sh /app/run.sh

# Mache das Start-Skript ausführbar
RUN chmod a+x /app/run.sh

# WICHTIG: Nicht ENTRYPOINT überschreiben!
# Wir nutzen CMD, damit das S6 Init-System des Base-Images aktiv bleibt.
CMD [ "/app/run.sh" ]
