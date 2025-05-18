import paramiko
import socket
import threading
import sys
import time
import logging
import inspect  # Import the inspect module

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Keep at DEBUG for maximum info
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

local_socket = None
running = True  # Added global flag for Ctrl+C


def start_reverse_tunnel(
    ssh_host,
    ssh_port,
    ssh_user,
    ssh_password,
    remote_bind_address,
    remote_port,
    local_host,
    local_port,
    use_key=False,
    ssh_key_path=None,
):
    """Sets up a reverse SSH tunnel."""
    client = None
    global local_socket
    global running  # Use the global running variable
    try:
        # Create an SSH client
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the SSH server
        logging.info(f"Connecting to {ssh_user}@{ssh_host}:{ssh_port}")
        if use_key:
            if ssh_key_path:
                try:
                    key = paramiko.RSAKey(filename=ssh_key_path)  # Or try other key types
                    client.connect(
                        ssh_host,
                        ssh_port,
                        username=ssh_user,
                        pkey=key,
                        timeout=10,
                    )
                except paramiko.ssh_exception.PasswordRequiredException:
                    logging.critical(
                        "Private key requires a passphrase.  Please provide the passphrase."
                    )
                    sys.exit(1)
                except paramiko.ssh_exception.SSHException as e:
                    logging.critical(f"Error reading private key: {e}")
                    sys.exit(1)
            else:
                logging.critical(
                    "Key-based authentication was selected, but no key path was provided."
                )
                sys.exit(1)
        else:
            client.connect(
                ssh_host,
                ssh_port,
                username=ssh_user,
                password=ssh_password,
                timeout=10,
            )

        # Create a transport
        transport = client.get_transport()
        if not transport or not transport.is_active():
            logging.critical("SSH transport is not active.")
            sys.exit(1)
        transport.set_keepalive(60)

        # Request the reverse port forward
        transport.request_port_forward(remote_bind_address, remote_port, local_host)
        logging.info(
            f"Reverse tunnel requested: {remote_bind_address}:{remote_port} -> {local_host}:{local_port}"
        )

        # Start listening on the local port
        local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        local_socket.bind((local_host, local_port))
        local_socket.listen(5)

        logging.info(f"Listening on {local_host}:{local_port}")

        while running:  # Main loop controlled by the running flag
            sock, addr = local_socket.accept()
            logging.info(f"Accepted connection from {addr[0]}:{addr[1]}")
            try:
                while True:
                    data = sock.recv(4096)
                    if not data:
                        break
                    logging.info(f"Received data: {data}")  # Log the received data
            except Exception as e:
                # Log the error with a clear prefix
                logging.error(f"ERROR in start_reverse_tunnel: {e}")
            finally:
                sock.close()

            if not transport.is_active():
                logging.warning("SSH transport disconnected.  Exiting.")
                break

    except paramiko.AuthenticationException:
        logging.error("Authentication failed.")
        sys.exit(1)
    except paramiko.SSHException as ssh_exception:
        logging.error(f"SSH error: {ssh_exception}")
        sys.exit(1)
    except socket.error as socket_error:
        logging.error(f"Socket error: {socket_error}")
        sys.exit(1)
    except KeyboardInterrupt:  # Handle Ctrl+C
        logging.info("Ctrl+C detected.  Exiting.")
        running = False  # Set the flag to false to exit the loop
    except Exception as e:
        # Log the error with a clear prefix
        logging.error(f"ERROR in start_reverse_tunnel: {e}")
        sys.exit(1)
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass
        if local_socket:
            try:
                local_socket.close()
            except Exception:
                pass
        logging.info("Connection closed.")


if __name__ == "__main__":
    # Replace with your actual connection details
    ssh_host = "146.190.96.130"
    ssh_port = 22
    ssh_user = "kev"
    ssh_password = "Ap0llo###"
    remote_bind_address = "0.0.0.0"
    remote_port = 7777
    local_host = "localhost"
    local_port = 7777
    use_key = False
    ssh_key_path = "/path/to/your/private_key"


    start_reverse_tunnel(
        ssh_host,
        ssh_port,
        ssh_user,
        ssh_password,
        remote_bind_address,
        remote_port,
        local_host,
        local_port,
        use_key=use_key,
        ssh_key_path=ssh_key_path,
    )
