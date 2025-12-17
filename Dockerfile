ARG BUILD_FROM
FROM $BUILD_FROM

# Pakete installieren
RUN apk add --no-cache python3 py3-pip

WORKDIR /app

# Pyserial direkt global installieren
RUN pip3 install --no-cache-dir --break-system-packages pyserial

# Dateien kopieren
COPY run.py .
COPY run.sh .

# Zeilenenden korrigieren (WICHTIG falls du auf Windows arbeitest)
RUN sed -i 's/\r$//' run.sh && chmod a+x run.sh

CMD [ "/app/run.sh" ]
