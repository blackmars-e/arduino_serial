import serial
import time
import socket

PORT = "/dev/ttyUSB0"
BAUD = 9600

def send(cmd):
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        ser.write((cmd+"\n").encode())
        time.sleep(0.2)

# TCP server auf Port 7070
sock = socket.socket()
sock.bind(("0.0.0.0", 7070))
sock.listen(5)
print("Arduino Serial Add-on ready")

while True:
    conn, addr = sock.accept()
    data = conn.recv(64).decode().strip()
    if data:
        print("Sending:", data)
        send(data)
    conn.close()
