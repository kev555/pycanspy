import socket
import time

REMOTE_HOST = '127.0.0.1'  # Or '127.0.0.1', referring to the VPS itself
REMOTE_PORT = 3332        # The REMOTE_PORT configured in the SSH tunnel

def run_sender():
    try:
        sender_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sender_socket.connect((REMOTE_HOST, REMOTE_PORT))
        print(f"Sender (on VPS) connected to {REMOTE_HOST}:{REMOTE_PORT}")

        while True:
            message = "Hello from client (on VPS)"
            sender_socket.sendall(message.encode())
            print(f"Sender sent: {message}")

            response = sender_socket.recv(1024)
            if not response:
                break
            print(f"Sender received: {response.decode()}")
            time.sleep(3)

    except socket.error as e:
        print(f"Socket error on sender (VPS): {e}")
    finally:
        if 'sender_socket' in locals():
            sender_socket.close()

if __name__ == "__main__":
    run_sender()