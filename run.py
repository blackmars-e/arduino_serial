import asyncio
import serial
import logging
import os
import signal

# Konfiguration
SERIAL_DEVICE = os.getenv("SERIAL_DEVICE", "/dev/ttyUSB0")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "9600"))
PORT = int(os.getenv("PORT", "7070"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ser = None
serial_queue = asyncio.Queue()

async def open_serial():
    global ser
    while True:
        try:
            if ser is None or not ser.is_open:
                ser = serial.Serial(SERIAL_DEVICE, SERIAL_BAUD, timeout=1)
                logging.info(f"✅ Seriell verbunden mit {SERIAL_DEVICE}")
            await asyncio.sleep(10) # Prüf-Intervall
        except Exception as e:
            logging.error(f"❌ Serial Fehler: {e}. Erneuter Versuch in 5s...")
            ser = None
            await asyncio.sleep(5)

async def handle_client(reader, writer):
    try:
        while True:
            data = await reader.read(1024)
            if not data:
                break
            cmd = data.decode().strip()
            logging.info(f"➡️ TCP Empfangen: {cmd}")
            if ser and ser.is_open:
                # Direktes Schreiben für weniger Latenz
                ser.write((cmd + "\n").encode())
                ser.flush()
                logging.info(f"✉️ Gesendet: {cmd}")
            else:
                logging.warning("⚠️ Serial nicht verbunden, Kommando verworfen")
    except Exception as e:
        logging.error(f"🌐 Client Fehler: {e}")
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    logging.info("🚀 Addon Initialisierung...")
    
    # Startet den Serial-Monitor im Hintergrund
    asyncio.create_task(open_serial())
    
    # Startet den Server
    server = await asyncio.start_server(handle_client, "0.0.0.0", PORT)
    logging.info(f"🌐 TCP Server auf Port {PORT} aktiv")

    async with server:
        # Dies hält das Skript für immer am Laufen
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"💥 Kritischer Absturz: {e}")
