import asyncio
import serial
import logging
import os
import time

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

PORT = 7070
SERIAL_DEVICE = "/dev/ttyUSB0"
SERIAL_BAUD = 9600
SERIAL_TIMEOUT = 1

QUEUE_SIZE = 100
BURST_MERGE_MS = 50
SERIAL_WRITE_TIMEOUT = 2

WATCHDOG_INTERVAL = 5

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

last_cmd = None
last_cmd_time = 0


# -------------------------------------------------
# SERIAL HANDLING
# -------------------------------------------------

async def open_serial():
    """Öffnet Serial robust mit Retry."""
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
            await asyncio.sleep(2)


async def write_serial_async(data: bytes):
    """Serial schreiben mit echtem Timeout (Thread wird abgebrochen, wenn er hängt)."""
    global ser

    if ser is None or not ser.is_open:
        await open_serial()

    try:
        # write + flush parallel im Thread
        await asyncio.wait_for(
            asyncio.to_thread(ser.write, data),
            timeout=SERIAL_WRITE_TIMEOUT
        )
        await asyncio.wait_for(
            asyncio.to_thread(ser.flush),
            timeout=SERIAL_WRITE_TIMEOUT
        )

        logging.info(f"✉️ Serial SEND: {data!r}")

    except Exception as e:
        logging.error(f"🚨 Serial Write Fehler: {e}")

        try:
            ser.close()
        except:
            pass

        ser = None


async def serial_worker():
    logging.info("👷 Serial Worker gestartet")

    while True:
        data = await serial_queue.get()

        try:
            await write_serial_async(data)
        except Exception as e:
            logging.error(f"🚫 Serial Worker Fehler: {e}")

        finally:
            serial_queue.task_done()


# -------------------------------------------------
# TCP SERVER HANDLER
# -------------------------------------------------

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global last_cmd, last_cmd_time

    addr = writer.get_extra_info("peername")
    logging.info(f"🔌 Client verbunden: {addr}")

    try:
        while True:
            try:
                data = await asyncio.wait_for(reader.read(1024), timeout=10)
            except asyncio.TimeoutError:
                logging.warning("⏱️ Client Timeout")
                break

            if not data:
                break

            cmd = data.decode(errors="ignore").strip()
            if not cmd:
                continue

            now = time.time() * 1000

            # Burst-Merge
            if cmd == last_cmd and (now - last_cmd_time) < BURST_MERGE_MS:
                logging.debug(f"⏭️ Burst-Merge skip: {cmd}")
                continue

            last_cmd = cmd
            last_cmd_time = now

            logging.info(f"➡️ Empfangen: {cmd}")

            payload = (cmd + "\n").encode()

            # Queue-Schutz: neue Befehle haben Priorität
            if serial_queue.full():
                _ = await serial_queue.get()
                serial_queue.task_done()
                logging.warning("⚠️ Queue voll → ältesten Befehl verworfen")

            await serial_queue.put(payload)

    except Exception as e:
        logging.error(f"🚫 TCP Fehler: {e}")

    finally:
        writer.close()
        await writer.wait_closed()
        logging.info(f"🔌 Client getrennt: {addr}")


# -------------------------------------------------
# WATCHDOG
# -------------------------------------------------

async def watchdog():
    global ser

    while True:
        try:
            q = serial_queue.qsize()

            if q > QUEUE_SIZE * 0.8:
                logging.warning(f"⚠️ Queue fast voll ({q}/{QUEUE_SIZE})")

            if ser and not ser.is_open:
                logging.error("⚠️ Serial geschlossen → reopen")
                await open_serial()

        except Exception as e:
            logging.error(f"🔥 Watchdog Fehler: {e}")

        await asyncio.sleep(WATCHDOG_INTERVAL)


# -------------------------------------------------
# MAIN
# -------------------------------------------------

async def main():
    logging.info("🚀 Addon startet")

    await open_serial()

    asyncio.create_task(serial_worker())
    asyncio.create_task(watchdog())

    server = await asyncio.start_server(handle_client, "0.0.0.0", PORT)
    logging.info(f"🌐 Async TCP Server aktiv auf Port {PORT}")

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Addon manuell beendet")
