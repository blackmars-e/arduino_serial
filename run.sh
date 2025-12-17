#!/usr/bin/env sh
set -e

echo "--- Starte Arduino Serial Controller ---"

# Zeige Pfade zur Fehlersuche im Log
echo "Python Version:"
python3 --version
echo "Installierte Pakete:"
pip3 list | grep pyserial

# Starte das Skript
exec python3 -u /app/run.py
