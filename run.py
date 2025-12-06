import logging
import socket
import serial
import os

# Debugging aktivieren (Optional, über ENV-Variable DEBUG=true)
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

logging.info("Arduino Serial Add-on gestartet...")

# TCP Server für Befehle
HOST = '127.0.0.1'  # alles hören
PORT = 7070

try:
    ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
    logging.info("Serielle Verbindung zu /dev/ttyUSB0 hergestellt")
except Exception as e:
    logging.error(f"Fehler beim Öffnen von /dev/ttyUSB0: {e}")
    ser = None

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen()
    logging.info(f"TCP Server hört auf {HOST}:{PORT}")

    while True:
        conn, addr = s.accept()
        with conn:
            logging.info(f"Verbindung von {addr}")
            data = conn.recv(1024)
            if data:
                command = data.decode().strip()
                logging.info(f"Empfangen: {command}")

                if ser:
                    try:
                        ser.write(data)
                        logging.info(f"An Arduino gesendet: {command}")
                    except Exception as e:
                        logging.error(f"Fehler beim Schreiben an Arduino: {e}")
                
                if DEBUG:
                    logging.info(f"DEBUG: Befehl {command} verarbeitet")
