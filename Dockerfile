ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Python + pip (Python ist meist schon da, pip nicht immer)
RUN apk add --no-cache python3 py3-pip

# pyserial via pip (leichtgewichtig, ok für HA)
RUN pip3 install --no-cache-dir pyserial==3.5

# Script kopieren
COPY run.py /app/run.py

# Start
CMD ["python3", "/app/run.py"]
