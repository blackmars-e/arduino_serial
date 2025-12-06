ARG BUILD_FROM
FROM $BUILD_FROM

RUN apk add --no-cache python3 py3-pip
RUN pip install pyserial

COPY run.py /run.py
CMD ["python3", "/run.py"]

