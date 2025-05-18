import socket
import time
import signal
import sys

LOCAL_HOST = 'localhost'
LOCAL_APP_PORT = 7777
SHUTDOWN_FLAG = False
ACTIVE_CONNECTION = None

def signal_handler(sig, frame):
    global SHUTDOWN_FLAG, ACTIVE_CONNECTION
    print("\nBasic server: Ctrl+C received. Shutting down...")
    SHUTDOWN_FLAG = True
    if ACTIVE_CONNECTION:
        try:
            ACTIVE_CONNECTION.shutdown(socket.SHUT_RDWR)
            ACTIVE_CONNECTION.close()
            print("Basic server: Active connection closed.")
        except OSError as e:
            print(f"Basic server: Error closing active connection: {e}")

def run_server():
    global SHUTDOWN_FLAG, ACTIVE_CONNECTION
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print("Basic server: Socket created.")
    try:
        server_socket.bind((LOCAL_HOST, LOCAL_APP_PORT))
        print(f"Basic server: Socket bound to {LOCAL_HOST}:{LOCAL_APP_PORT}")
        server_socket.listen(1)
        print(f"Basic server: Listening on {LOCAL_HOST}:{LOCAL_APP_PORT}")

        server_socket.settimeout(1)  # Set timeout for accept()

        while not SHUTDOWN_FLAG:
            try:
                print("Basic server: Waiting to accept connection...")
                conn, addr = server_socket.accept()
                print(f"Basic server: Connection accepted from {addr}")
                ACTIVE_CONNECTION = conn
                conn.settimeout(1)  # Set timeout for connection recv/send

                while not SHUTDOWN_FLAG:
                    try:
                        data = conn.recv(1024)
                        if not data:
                            print("Basic server: Client closed the connection.")
                            break
                        print(f"Basic server received: {data.decode()}")

                        message_to_send = "Hello from server (through tunnel)"
                        conn.sendall(message_to_send.encode())
                        print(f"Basic server sent: {message_to_send}")

                        time.sleep(3)
                    except socket.timeout:
                        pass  # No data received within timeout, check shutdown flag
                    except ConnectionResetError:
                        print("Basic server: Client forcibly closed the connection.")
                        break
                    except Exception as e:
                        print(f"Basic server error during communication: {e}")
                        break

                print("Basic server: About to close the connection.")
                conn.close()
                print("Basic server: Connection closed.")
                ACTIVE_CONNECTION = None

            except socket.timeout:
                pass  # No connection within timeout, check shutdown flag
            except socket.error as e:
                print(f"Basic server error: {e}")
                break
            except Exception as e:
                print(f"Basic server main loop error: {e}")
                break

    except socket.error as e:
        print(f"Basic server error during setup: {e}")
    finally:
        print("Basic server: About to close the server socket.")
        try:
            server_socket.close()
            print("Basic server: Server socket closed.")
        except:
            print("Basic server: Error closing server socket.")

if __name__ == "__main__":
    print("Basic server: Starting...")
    signal.signal(signal.SIGINT, signal_handler)
    print("Basic server: Signal handler registered.")
    run_server()
    print("Basic server: Finished.")