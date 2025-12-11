#!/usr/bin/env python3
"""
Robustes AsyncIO Addon - stabilere Version
- Überwacht Hintergrund-Tasks und startet sie neu falls sie crashen
- Robuste serielle Verbindung mit Retry / Backoff
- Thread-safe Serial-Writes mit Timeout & Retry
- TCP-Server für eingehende Kommandos
- Sauberes Signal-Handling für Shutdown
- Verbesserte Logging-Ausgaben (DE)
"""

import asyncio
import serial
import logging
import os
import time
import signal
import sys
from typing import Optional

# -------------------------------------------------
# CONFIG
# -------------------------------------------------

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

PORT = int(os.getenv("PORT", "7070"))
SERIAL_DEVICE = os.getenv("SERIAL_DEVICE", "/dev/ttyUSB0")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "9600"))
SERIAL_TIMEOUT = float(os.getenv("SERIAL_TIMEOUT", "1"))

QUEUE_SIZE = int(os.getenv("QUEUE_SIZE", "100"))
BURST_MERGE_MS = int(os.getenv("BURST_MERGE_MS", "50"))
SERIAL_WRITE_TIMEOUT = float(os.getenv("SERIAL_WRITE_TIMEOUT", "2"))
SERIAL_OPEN_RETRY_BASE = float(os.getenv("SERIAL_OPEN_RETRY_BASE", "1.0"))  # seconds
SERIAL_MAX_RETRIES = int(os.getenv("SERIAL_MAX_RETRIES", "5"))

WATCHDOG_INTERVAL = float(os.getenv("WATCHDOG_INTERVAL", "5"))

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

ser: Optional[serial.Serial] = None
serial_queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
serial_lock = asyncio.Lock()  # stellt sicher, dass nur ein Schreibthread gleichzeitig schreibt

last_cmd = None
last_cmd_time = 0

shutdown_event = asyncio.Event()

# keep references to runtime tasks so monitor can restart them
runtime_tasks: dict = {}

# -------------------------------------------------
# HELPERS
# -------------------------------------------------


def now_ms() -> float:
    return time.time() * 1000.0


async def safe_sleep(seconds: float):
    """Sleep that wakes early on shutdown."""
    try:
        await asyncio.wait_for(shutdown_event.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        return


# -------------------------------------------------
# SERIAL HANDLING (robust)
# -------------------------------------------------


async def open_serial():
    """
    Öffnet die serielle Verbindung robust mit Exponential-Backoff.
    Gibt nur zurück, wenn ser erfolgreich geöffnet wurde oder shutdown.
    """
    global ser
    retry = 0
    while not shutdown_event.is_set():
        try:
            ser = serial.Serial(
                SERIAL_DEVICE,
                SERIAL_BAUD,
                timeout=SERIAL_TIMEOUT
            )
            logging.info("✅ Seriell verbunden")
            return
        except Exception as e:
            retry += 1
            wait = SERIAL_OPEN_RETRY_BASE * (2 ** (retry - 1))
            if retry > SERIAL_MAX_RETRIES:
                # danach weiter versuchen, aber mit cap auf lange Wartezeit
                wait = min(wait, 60)
            logging.error(f"❌ Seriell fehlgeschlagen (Versuch {retry}): {e} — retry in {wait:.1f}s")
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=wait)
                return
            except asyncio.TimeoutError:
                continue


async def close_serial_quiet():
    """Versuche ser.close() ohne Ausnahme."""
    global ser
    try:
        if ser:
            try:
                ser.close()
            except Exception:
                pass
    finally:
        ser = None


async def write_serial_async(data: bytes):
    """
    Seriell schreiben mit Timeout & Lock. Wenn Fehler, versuchen wir Reopen und mehrere Retries.
    Diese Funktion wirft nicht hoch; Fehler werden geloggt.
    """
    global ser

    if shutdown_event.is_set():
        logging.debug("✉️ Ignoriere Serial-Send während Shutdown")
        return

    # Wir brauchen eine lock: nur ein Writer interfaced zum pyserial gleichzeitig
    async with serial_lock:
        attempts = 0
        while attempts < 3 and not shutdown_event.is_set():
            attempts += 1
            if ser is None or not getattr(ser, "is_open", False):
                logging.warning("⚠️ Serial nicht offen — versuche Reopen vor Write")
                await open_serial()
                if ser is None:
                    logging.error("⚠️ Reopen fehlgeschlagen, retry später")
                    await safe_sleep(1)
                    continue

            try:
                # Schreibe in Thread mit Timeout
                await asyncio.wait_for(
                    asyncio.to_thread(ser.write, data),
                    timeout=SERIAL_WRITE_TIMEOUT
                )
                await asyncio.wait_for(
                    asyncio.to_thread(ser.flush),
                    timeout=SERIAL_WRITE_TIMEOUT
                )

                logging.info(f"✉️ Serial SEND: {data!r}")
                return  # success

            except asyncio.TimeoutError:
                logging.error("🚨 Serial Write Timeout")
                # versuche Serial zu schließen und neu zu öffnen
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                await safe_sleep(0.5 * attempts)

            except Exception as e:
                logging.error(f"🚨 Serial Write Fehler (Attempt {attempts}): {e}")
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                await safe_sleep(0.5 * attempts)

        # wenn wir hier sind, alle attempts fehlgeschlagen
        logging.error("🔴 Serial Write: Alle Versuche fehlgeschlagen — Befehl verworfen")


async def serial_worker():
    """
    Worker: liest von serial_queue und sendet per write_serial_async.
    Er crash't nicht — schützt sich selbst, protokolliert Fehler.
    """
    logging.info("👷 Serial Worker gestartet")
    try:
        while not shutdown_event.is_set():
            try:
                data = await asyncio.wait_for(serial_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue  # wieder prüfen ob shutdown

            try:
                await write_serial_async(data)
            except Exception as e:
                logging.error(f"🚫 Serial Worker Fehler bei Send: {e}")
            finally:
                try:
                    serial_queue.task_done()
                except Exception:
                    pass

    except Exception as e:
        logging.exception(f"🔥 Unhandled error in serial_worker: {e}")
        raise  # damit Monitor reagieren kann

# -------------------------------------------------
# TCP SERVER HANDLER
# -------------------------------------------------


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """
    pro-Client Handler: liest Commands (bis 1024 bytes), macht Burst-Merge, pusht in Queue
    """
    global last_cmd, last_cmd_time

    addr = writer.get_extra_info("peername")
    logging.info(f"🔌 Client verbunden: {addr}")

    try:
        while not shutdown_event.is_set():
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

            now = now_ms()

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
                # ältesten löschen
                try:
                    _ = serial_queue.get_nowait()
                    serial_queue.task_done()
                    logging.warning("⚠️ Queue voll → ältesten Befehl verworfen")
                except Exception:
                    logging.warning("⚠️ Queue voll aber entfernen fehlgeschlagen")

            try:
                await serial_queue.put(payload)
            except Exception as e:
                logging.error(f"🚨 Fehler beim put in serial_queue: {e}")

    except Exception as e:
        logging.exception(f"🚫 TCP Fehler (Client {addr}): {e}")

    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        logging.info(f"🔌 Client getrennt: {addr}")


async def server_loop():
    """
    Startet den TCP-Server und führt serve_forever in einer Schleife aus.
    Falls start_server fehlschlägt, versuchen wir es erneut nach Delay.
    Fehler werden geloggt — der Task versucht nicht, den ganzen Prozess zu beenden.
    """
    logging.info("🌐 Server Loop gestartet")
    retry = 0
    while not shutdown_event.is_set():
        try:
            server = await asyncio.start_server(handle_client, "0.0.0.0", PORT)
            logging.info(f"🌐 Async TCP Server aktiv auf Port {PORT}")
            # serve_forever blockiert; wenn es eine Exception wirft, gehen wir in except
            async with server:
                retry = 0
                await server.serve_forever()
        except asyncio.CancelledError:
            logging.info("🌐 Server Loop cancelled")
            raise
        except Exception as e:
            retry += 1
            wait = min(5 * retry, 60)
            logging.exception(f"🚨 TCP Server Fehler: {e} — restart in {wait}s")
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=wait)
                break
            except asyncio.TimeoutError:
                continue

    logging.info("🌐 Server Loop beendet")


# -------------------------------------------------
# WATCHDOG
# -------------------------------------------------


async def watchdog():
    """
    Überwacht Queue-Größe und seriellen Zustand.
    Versucht nur Reopen / Log — wir werfen nicht.
    """
    logging.info("👁️ Watchdog gestartet")
    try:
        while not shutdown_event.is_set():
            try:
                q = serial_queue.qsize()

                if q > QUEUE_SIZE * 0.8:
                    logging.warning(f"⚠️ Queue fast voll ({q}/{QUEUE_SIZE})")

                if ser and not getattr(ser, "is_open", False):
                    logging.error("⚠️ Serial geschlossen → reopen")
                    await open_serial()

            except Exception as e:
                logging.exception(f"🔥 Watchdog Fehler: {e}")

            await safe_sleep(WATCHDOG_INTERVAL)
    except asyncio.CancelledError:
        logging.info("👁️ Watchdog cancelled")
        raise
    except Exception:
        logging.exception("🔥 Unhandled error in watchdog")
        raise


# -------------------------------------------------
# TASK MONITORING / SUPERVISION
# -------------------------------------------------


async def monitor_task(name: str, coro_factory, restart_delay: float = 1.0):
    """
    Überwacht eine coroutine (factory-funktion, die eine coroutine zurückgibt).
    Wenn sie beendet (außer Shutdown), wird sie nach restart_delay neu gestartet.
    """
    logging.info(f"🛡️ Monitor startet Task '{name}'")
    while not shutdown_event.is_set():
        task = asyncio.create_task(coro_factory())
        runtime_tasks[name] = task
        try:
            await task
            # task beendet ohne Exception
            if shutdown_event.is_set():
                logging.info(f"🛡️ Task '{name}' beendet wegen Shutdown")
                break
            logging.warning(f"🛡️ Task '{name}' beendet unerwartet ohne Exception — restart in {restart_delay}s")
        except asyncio.CancelledError:
            logging.info(f"🛡️ Task '{name}' Cancelled")
            raise
        except Exception as e:
            logging.exception(f"🛡️ Task '{name}' crashed: {e} — restart in {restart_delay}s")
        finally:
            runtime_tasks.pop(name, None)

        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=restart_delay)
            break
        except asyncio.TimeoutError:
            continue

    logging.info(f"🛡️ Monitor stoppt Task '{name}'")


# -------------------------------------------------
# SIGNAL HANDLING
# -------------------------------------------------


def _handle_terminate_signals():
    """Signal-Handler: setzt shutdown_event."""
    if not shutdown_event.is_set():
        logging.info("🛑 SIG received → Shutdown wird eingeleitet")
        shutdown_event.set()


def setup_signal_handlers(loop):
    try:
        loop.add_signal_handler(signal.SIGTERM, _handle_terminate_signals)
        loop.add_signal_handler(signal.SIGINT, _handle_terminate_signals)
    except NotImplementedError:
        # Windows: loop.add_signal_handler kann NotImplementedError werfen
        signal.signal(signal.SIGTERM, lambda *_: _handle_terminate_signals())
        signal.signal(signal.SIGINT, lambda *_: _handle_terminate_signals())


# -------------------------------------------------
# MAIN
# -------------------------------------------------


async def main():
    logging.info("🚀 Addon startet (stabile Version)")

    # Setup signal handling
    setup_signal_handlers(asyncio.get_running_loop())

    # Versuche initial Serial aufzubauen (non-blocking fallback handled by open_serial)
    asyncio.create_task(open_serial())

    # Starte überwachte Tasks: serial_worker, watchdog, server_loop
    monitors = [
        asyncio.create_task(monitor_task("serial_worker", lambda: serial_worker(), restart_delay=1.0)),
        asyncio.create_task(monitor_task("watchdog", lambda: watchdog(), restart_delay=2.0)),
        asyncio.create_task(monitor_task("server_loop", lambda: server_loop(), restart_delay=2.0)),
    ]

    # Warten bis shutdown_event gesetzt
    try:
        await shutdown_event.wait()
        logging.info("🛑 Shutdown event empfangen. Stoppe Tasks...")
    except asyncio.CancelledError:
        logging.info("🛑 main cancelled")

    # Graceful shutdown: cancel monitors and any running runtime tasks
    for m in monitors:
        m.cancel()
    for name, t in list(runtime_tasks.items()):
        logging.info(f"🧯 Cancel runtime task {name}")
        try:
            t.cancel()
        except Exception:
            pass

    # give tasks small time to cancel
    await asyncio.sleep(0.2)

    # close serial
    await close_serial_quiet()

    # flush queue (optional)
    try:
        while not serial_queue.empty():
            try:
                _ = serial_queue.get_nowait()
                serial_queue.task_done()
            except Exception:
                break
    except Exception:
        pass

    logging.info("✅ Addon sauber beendet")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.exception(f"🔴 Unerwarteter Fehler in __main__: {e}")
        # damit man im Container-/Supervisor-Log sehen kann, warum, dann exit(1)
        sys.exit(1)
