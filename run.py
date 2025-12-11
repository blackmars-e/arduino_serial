import asyncio
import serial_asyncio
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

QUEUE_SIZE = 100
BURST_MERGE_MS = 50           # Befehle innerhalb von 50ms mit gleichem Inhalt werden gemerged
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

serial_writer = None
serial_queue = asyncio.Queue(maxsize=QUEUE_SIZE)

last_command = None
last_command_time = 0


# -------------------------------------------------
# SERIAL HANDLING
# -------------------------------------------------

async def open_serial():
    """Öffnet den Serial-Port async & robust mit Retry."""
    global serial_writer

    while True:
        try:
            reader, writer = await serial_asyncio.open_serial_connection(
                url=SERIAL_DEVICE,
                baudrate=SERIAL_BAUD
            )

            serial_writer = writer
            logging.info("✅ Seriell verbunden")
            return

        except Exception as e:
            logging.error(f"❌ Seriell fehlgeschlagen: {e}")
            await asyncio.sleep(2)


async def serial_worker():
    """Nimmt Befehle aus der Queue und sendet sie ans Gerät."""
    global serial_writer

    logging.info("👷 Serial Worker gestartet")

    while True:
        command = await serial_queue.get()

        try:
            if serial_writer is None:
                await open_serial()

            serial_writer.write(command)
            await serial_writer.drain()

            logging.info(f"✉️ Serial SEND: {command!r}")

        except Exception as e:
            logging.error(f"🚨 Serial Fehler: {e}")
            serial_writer = None

        finally:
            serial_queue.task_done()


# -------------------------------------------------
# TCP SERVER HANDLER
# -------------------------------------------------

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global last_command, last_command_time

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

            command = data.decode(errors="ignore").strip()
            if not command:
                continue

            now = time.time() * 1000

            # Burst-Merging: gleiche Commands / kurze Zeit → skip
            if command == last_command and now - last_command_time < BURST_MERGE_MS:
                logging.debug(f"⏭️ Burst-Merge skip: {command}")
                continue

            last_command = command
            last_command_time = now

            logging.info(f"➡️ Empfangen: {command}")

            payload = (command + "\n").encode()

            # Queue mit Priorität (neue bevorzugt)
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
    while True:
        try:
            qn = serial_queue.qsize()
            if qn > QUEUE_SIZE * 0.8:
                logging.warning(f"⚠️ Queue fast voll ({qn}/{QUEUE_SIZE})")

            if serial_writer is None:
                logging.warning("⚠️ Serial nicht verbunden → reopen")
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
