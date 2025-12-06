ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM $BUILD_FROM

# Install Python + pyserial
RUN apk add --no-cache python3 py3-pip py3-serial

# Copy the script
COPY run.py /run.py

# Start the Python script
CMD ["python3", "/run.py"]
