# Wir nutzen die Variable BUILD_FROM, damit Home Assistant automatisch
# das richtige Base-Image für deinen Pi (armv7 oder aarch64) wählt.
ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Python und Pip installieren
RUN apk add --no-cache python3 py3-pip

# Virtual Environment erstellen (Best Practice bei Alpine Linux)
RUN python3 -m venv /opt/venv

# PySerial im venv installieren
RUN /opt/venv/bin/pip install --upgrade pip pyserial

# Script kopieren
COPY run.py /app/run.py

# WICHTIG: CMD verwenden statt ENTRYPOINT für S6-Overlay Support
# WICHTIG: "-u" Flag nutzen, sonst bleiben die Logs leer bei einem Crash!
CMD ["/opt/venv/bin/python3", "-u", "/app/run.py"]
