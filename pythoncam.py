import cv2
import socket
import struct
import pickle

HOST = "0.0.0.0"
PORT = 5000

cap = cv2.VideoCapture("/dev/video0", cv2.CAP_V4L2)

cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)

if not cap.isOpened():
    raise RuntimeError("No se pudo abrir la cámara")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen(1)

print(f"Esperando conexión en el puerto {PORT}...")

conn, addr = server.accept()
print(f"Conectado: {addr}")

try:
    while True:
        ret, frame = cap.read()

        if not ret:
            print("No se pudo leer un frame")
            break

        # Comprimir el frame como JPEG
        ok, encoded = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 80]
        )

        if not ok:
            continue

        data = encoded.tobytes()

        # Enviar tamaño + imagen
        conn.sendall(struct.pack("!I", len(data)))
        conn.sendall(data)

except (BrokenPipeError, ConnectionResetError):
    print("Cliente desconectado")

finally:
    cap.release()
    conn.close()
    server.close()
