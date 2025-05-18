
# Send dummy cv generated frames, no need to use webcam
# Great for dev testing without starting up the GUI / Manang camera processes

import socket
import pickle
import struct
import threading
import queue
import numpy as np
import time
import cv2

# Server setup
HOST = '127.0.0.1'
PORT = 5000
frame_queue = queue.Queue()

###

def generate_fake_frames():
    while True:
        # Create a fake frame (e.g., 480x640 RGB image with random data)
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        frame_queue.put(frame)
        time.sleep(0.1)  # simulate ~10 FPS

###

def send_frames_to_client(conn):
    while True:
        try:
            frame = frame_queue.get(timeout=1)
        except queue.Empty:
            continue

        success, encoded_frame = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50]) # encode it now, before transmitting!!
        if not success:
            raise RuntimeError("Failed to encode frame")

        try:
            data = pickle.dumps(encoded_frame)
            message_size = struct.pack("!I", len(data))  # 4-byte unsigned int, network byte order
            conn.sendall(message_size + data)
        except Exception as e:
            print(f"[Sender] Error sending frame: {e}")
            break

def main():
    print("[Main] Starting fake video sender...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"[Main] Listening on {HOST}:{PORT}")

    conn, addr = s.accept()
    print(f"[Main] Connection from {addr}")

    # Optional: wait for the 'start_server_view\n' command from client
    try:
        init_msg = conn.recv(1024).decode()
        print(f"[Main] Got init message: {init_msg.strip()}")
    except:
        pass

    # Start threads
    threading.Thread(target=generate_fake_frames, daemon=True).start()
    threading.Thread(target=send_frames_to_client, args=(conn,), daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[Main] Shutting down...")
        conn.close()
        s.close()

if __name__ == "__main__":
    main()
