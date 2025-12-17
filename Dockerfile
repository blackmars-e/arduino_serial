ARG BUILD_FROM
FROM $BUILD_FROM

# Installiere Abhängigkeiten
RUN apk add --no-cache python3 py3-pip

# Installiere pyserial global
RUN pip3 install --no-cache-dir --break-system-packages pyserial

WORKDIR /app
COPY run.py .
COPY run.sh .

RUN chmod a+x /app/run.sh

# WICHTIG: Nutze S6-Overlay korrekt
CMD [ "/app/run.sh" ]
