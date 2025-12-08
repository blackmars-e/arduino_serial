import asyncio
import serial
import logging
import os

DEBUG = os.getenv("DEBUG", "false").lower() == "true"
PORT = 7070

logging.basicConfig(
    format='%(asctime)s - %(message)s',
    level=logging.INFO
)

ser = None
serial_queue = asyncio.Queue()


# ---------- SERIAL HANDLING ----------

async def open_serial():
    global ser

    while True:
        try:
            ser = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
            logging.info("✅ Seriell verbunden")
            return
        except Exception as e:
            logging.error(f"❌ Seriell fehlgeschlagen: {e}")
            await asyncio.sleep(3)


async def write_serial(data: bytes):
    global ser

    if not ser:
        await open_serial()

    try:
        # Non-blocking write
        await asyncio.to_thread(ser.write, data)
        await asyncio.to_thread(ser.flush)
    except Exception as e:
        logging.error(f"🚨 USB Fehler: {e}")
        try:
            ser.close()
        except:
            pass
        ser = None


async def serial_worker():
    while True:
        data = await serial_queue.get()
        await write_serial(data)
        serial_queue.task_done()


# ---------- TCP SERVER ----------

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    logging.info(f"🔌 Client verbunden: {addr}")

    try:
        while True:
            data = await asyncio.wait_for(reader.read(1024), timeout=10)

            if not data:
                break

            command = data.decode(errors='ignore').strip()
            logging.info(f"➡️  Empfangen: {command}")

            # Zeilenende sicherstellen
            data_to_send = (command + '\n').encode()
            await serial_queue.put(data_to_send)

            if DEBUG:
                logging.info(f"DEBUG verarbeitet: {command}")

    except asyncio.TimeoutError:
        logging.warning("⏱️ Client Timeout")
    except Exception as e:
        logging.error(f"TCP Fehler: {e}")

    writer.close()
    await writer.wait_closed()
    logging.info("🔌 Client getrennt")


# ---------- WATCHDOG HEARTBEAT ----------

async def heartbeat():
    while True:
        logging.debug("💓 heartbeat")
        await asyncio.sleep(10)


# ---------- MAIN ----------

async def main():

    await open_serial()

    # Starte Serial-Worker
    asyncio.create_task(serial_worker())

    server = await asyncio.start_server(
        handle_client,
        host="0.0.0.0",
        port=PORT
    )

    logging.info(f"🚀 Async TCP Server läuft auf Port {PORT}")

    asyncio.create_task(heartbeat())

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
