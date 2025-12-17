#!/bin/sh
set -e

echo "Starte Arduino Serial Controller..."

# Starte Python im Unbuffered Mode (-u), damit Logs sofort sichtbar sind
# exec ersetzt den aktuellen Shell-Prozess durch Python (wichtig für Signale)
exec /opt/venv/bin/python3 -u /app/run.py
