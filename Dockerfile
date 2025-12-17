ARG BUILD_FROM
FROM $BUILD_FROM

# Pakete installieren
RUN apk add --no-cache \
    python3 \
    py3-pip

WORKDIR /app

# Direkt installieren ohne Venv (im Container oft stabiler für Add-ons)
RUN pip3 install --no-cache-dir --break-system-packages pyserial

COPY run.py .
COPY run.sh .

RUN sed -i 's/\r$//' run.sh && chmod a+x run.sh

CMD [ "/app/run.sh" ]
