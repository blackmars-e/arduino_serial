#!/usr/bin/env sh
set -e

echo "--- Starte Arduino Serial Controller Add-on ---"
echo "Prüfe Hardware..."
if [ -c "/dev/ttyUSB0" ]; then
    echo "✅ /dev/ttyUSB0 gefunden."
else
    echo "⚠️ /dev/ttyUSB0 nicht gefunden! Das Skript wird versuchen, sich zu verbinden, sobald es verfügbar ist."
fi

# Starte Python Skript
exec python3 -u /app/run.py
