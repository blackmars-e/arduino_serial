import logging
import socket
import serial
import os
import time

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

HOST = "0.0.0.0"
PORT = 7070


def open_serial():
    try:
        ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
        logging.info("Serielle Verbindung hergestellt")
        return ser
    except Exception as e:
        logging.error(f"Serielle Verbindung fehlgeschlagen: {e}")
        return None


ser = open_serial()

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    s.settimeout(5)

    logging.info(f"TCP Server aktiv auf {HOST}:{PORT}")

    while True:
        try:
            conn, addr = s.accept()
        except socket.timeout:
            # Watchdog-Pulse
            logging.debug("Heartbeat")
            continue

        with conn:
            conn.settimeout(5)
            logging.info(f"Verbindung von {addr}")

            try:
                data = conn.recv(1024)
            except socket.timeout:
                continue

            if not data:
                continue

            command = data.decode(errors="ignore").strip()
            logging.info(f"Empfangen: {command}")

            if ser:
                try:
                    ser.write(data)
                    ser.flush()
                except Exception as e:
                    logging.error(f"USB Fehler -> Neuverbinden: {e}")
                    try:
                        ser.close()
                    except:
                        pass

                    time.sleep(1)
                    ser = open_serial()

            if DEBUG:
                logging.info(f"DEBUG verarbeitet: {command}")
