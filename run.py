import asyncio
import serial
import logging
import os

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

PORT = 7070
SERIAL_DEVICE = "/dev/ttyUSB0"
SERIAL_BAUD = 9600
SERIAL_TIMEOUT = 1

QUEUE_SIZE = 100           # ✅ RAM SAFE
SERIAL_WRITE_TIMEOUT = 2  # ✅ USB Freeze Schutz
SERIAL_RETRY_DELAY = 3

# -------------------------------------------------
# LOGGING
# -------------------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG if DEBUG else logging.INFO
)

# -------------------------------------------------
# GLOBALS
# -------------------------------------------------

ser = None
serial_queue = asyncio.Queue(maxsize=QUEUE_SIZE)

# -------------------------------------------------
# SERIAL HANDLING
# -------------------------------------------------

async def open_serial():
    global ser

    while True:
        try:
            ser = serial.Serial(
                SERIAL_DEVICE,
                SERIAL_BAUD,
                timeout=SERIAL_TIMEOUT
            )
            logging.info("✅ Seriell verbunden")
            return

        except Exception as e:
            logging.error(f"❌ Seriell fehlgeschlagen: {e}")
            await asyncio.sleep(SERIAL_RETRY_DELAY)


async def write_serial(data: bytes):
    global ser

    if ser is None or not ser.is_open:
        logging.warning("🔌 Seriell nicht verbunden → Reconnect")
        await open_serial()

    try:
        await asyncio.wait_for(
            asyncio.to_thread(ser.write, data),
            timeout=SERIAL_WRITE_TIMEOUT
        )
        await asyncio.to_thread(ser.flush)

    except Exception as e:
        logging.error(f"🚨 USB Fehler: {e}")

        try:
            ser.close()
        except:
            pass

        ser = None

        # Reconnect
        await open_serial()


async def serial_worker():
    logging.info("👷 Serial Worker gestartet")

    while True:
        data = await serial_queue.get()

        try:
            await write_serial(data)
        except Exception as e:
            logging.error(f"🚫 Serial Worker Fehler: {e}")

        finally:
            serial_queue.task_done()


# -------------------------------------------------
# TCP SERVER HANDLER
# -------------------------------------------------

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    addr = writer.get_extra_info("peername")
    logging.info(f"🔌 Client verbunden: {addr}")

    try:
        while True:
            data = await asyncio.wait_for(reader.read(1024), timeout=10)

            if not data:
                break

            command = data.decode(errors="ignore").strip()

            if not command:
                continue

            logging.info(f"➡️  Empfangen: {command}")

            payload = (command + '\n').encode()

            try:
                await serial_queue.put(payload)
            except asyncio.QueueFull:
                logging.warning("⚠️ Serial Queue voll → Kommando verworfen")

    except asyncio.TimeoutError:
        logging.warning("⏱️ Client Timeout")

    except Exception as e:
        logging.error(f"🚫 TCP Fehler: {e}")

    finally:
        writer.close()
        await writer.wait_closed()
        logging.info(f"🔌 Client getrennt: {addr}")


# -------------------------------------------------
# WATCHDOG / HEARTBEAT
# -------------------------------------------------

async def heartbeat():
    while True:
        logging.debug("💓 heartbeat ok")
        await asyncio.sleep(10)


async def resource_monitor():
    """Mini-Watchdog für Queue & Serial"""

    while True:
        try:
            qsize = serial_queue.qsize()

            if qsize > QUEUE_SIZE * 0.8:
                logging.warning(f"⚠️ Queue fast voll ({qsize}/{QUEUE_SIZE})")

            if ser and not ser.is_open:
                logging.warning("⚠️ Serial port geschlossen → reopen")
                await open_serial()

        except Exception as e:
            logging.error(f"🔥 Watchdog Fehler: {e}")

        await asyncio.sleep(5)


# -------------------------------------------------
# MAIN LOOP
# -------------------------------------------------

async def main():
    logging.info("🚀 Addon startet")

    # Initial serial connect
    await open_serial()

    # Workers starten
    asyncio.create_task(serial_worker())
    asyncio.create_task(heartbeat())
    asyncio.create_task(resource_monitor())

    # TCP Server starten
    server = await asyncio.start_server(
        handle_client,
        host="0.0.0.0",
        port=PORT
    )

    logging.info(f"🌐 Async TCP Server aktiv auf Port {PORT}")

    async with server:
        await server.serve_forever()


# -------------------------------------------------
# ENTRYPOINT
# -------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Addon manuell beendet")
