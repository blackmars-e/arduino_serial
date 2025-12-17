import asyncio
import serial
import logging
import os
import time
import signal
import sys
from typing import Optional

# Konfiguration via Umgebungsvariablen (von HA gesetzt)
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
PORT = int(os.getenv("PORT", "7070"))
SERIAL_DEVICE = os.getenv("SERIAL_DEVICE", "/dev/ttyUSB0")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "9600"))

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG if DEBUG else logging.INFO
)

ser: Optional[serial.Serial] = None
serial_queue = asyncio.Queue(maxsize=100)
serial_lock = asyncio.Lock()
shutdown_event = asyncio.Event()

async def open_serial():
    global ser
    while not shutdown_event.is_set():
        try:
            ser = serial.Serial(SERIAL_DEVICE, SERIAL_BAUD, timeout=1)
            logging.info(f"✅ Seriell verbunden mit {SERIAL_DEVICE}")
            return
        except Exception as e:
            logging.error(f"❌ Verbindung zu {SERIAL_DEVICE} fehlgeschlagen: {e}. Retry in 5s...")
            await asyncio.sleep(5)

async def write_serial_async(data: bytes):
    global ser
    async with serial_lock:
        try:
            if ser and ser.is_open:
                await asyncio.to_thread(ser.write, data)
                await asyncio.to_thread(ser.flush)
                logging.info(f"✉️ Gesendet: {data!r}")
            else:
                logging.warning("⚠️ Serial nicht bereit, überspringe Senden.")
        except Exception as e:
            logging.error(f"🚨 Fehler beim Schreiben: {e}")
            ser = None # Trigger Reopen im Watchdog

async def serial_worker():
    while not shutdown_event.is_set():
        try:
            data = await asyncio.wait_for(serial_queue.get(), timeout=1.0)
            await write_serial_async(data)
            serial_queue.task_done()
        except asyncio.TimeoutError:
            continue

async def handle_client(reader, writer):
    try:
        data = await reader.read(1024)
        if data:
            cmd = data.decode().strip()
            logging.info(f"➡️ TCP Empfangen: {cmd}")
            await serial_queue.put((cmd + "\n").encode())
    finally:
        writer.close()

async def main():
    logging.info("🚀 Addon Initialisierung...")
    
    # Serial im Hintergrund starten, damit TCP-Server sofort bereit ist (Watchdog!)
    asyncio.create_task(open_serial())
    
    # Worker & Server starten
    server = await asyncio.start_server(handle_client, "0.0.0.0", PORT)
    logging.info(f"🌐 TCP Server auf Port {PORT} aktiv")

    async with server:
        worker_task = asyncio.create_task(serial_worker())
        await shutdown_event.wait()
        worker_task.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
