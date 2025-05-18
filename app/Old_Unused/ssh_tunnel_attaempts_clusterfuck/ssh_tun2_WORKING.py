import paramiko
import socket
import threading
import sys
import time
import logging
import inspect  # Import the inspect module

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

local_socket = None


def forward_local(local_port, remote_host, remote_port, transport):
    """Handles the forwarding of a single connection."""
    global local_socket
    try:
        sock, addr = local_socket.accept()
        logging.info(f"Accepted connection from {addr[0]}:{addr[1]} on local port {local_port}")
    except Exception as e:
        logging.error(f"Error accepting connection on local port {local_port}: {e}")
        return

    channel = None
    try:
        channel = transport.open_channel("direct-tcpip", (remote_host, remote_port), sock.getpeername())
        logging.debug(f"Opened channel to {remote_host}:{remote_port}")
    except Exception as e:
        logging.error(
            f"Could not connect to {remote_host}:{remote_port} from " f"local port {local_port}: {e}"
        )
        sock.close()
        return

    if channel is None:
        logging.error(
            "Channel is None.  This likely means the remote SSH server rejected the connection."
        )
        sock.close()
        return

    sock.settimeout(5)
    channel.settimeout(5)

    def handler(r_sock, w_sock):
        while True:
            try:
                data = r_sock.recv(4096)
                if not data:
                    break
                w_sock.send(data)
            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"Error forwarding data: {e}")
                break
        r_sock.close()
        w_sock.close()

    t1 = threading.Thread(target=handler, args=(sock, channel))
    t2 = threading.Thread(target=handler, args=(channel, sock))
    t1.start()
    t2.start()


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
                    logging.critical("Private key requires a passphrase.  Please provide the passphrase.")
                    sys.exit(1)
                except paramiko.ssh_exception.SSHException as e:
                    logging.critical(f"Error reading private key: {e}")
                    sys.exit(1)
            else:
                logging.critical("Key-based authentication was selected, but no key path was provided.")
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

        logging.debug(f"Transport is active: {transport.is_active()}")
        logging.debug(f"Transport: {transport}")
        logging.debug(f"Transport methods: {dir(transport)}")

        # Check for correct method based on version
        if hasattr(transport, "request_tcp_forward"):
            try:
                transport.request_tcp_forward(remote_bind_address, remote_port)
                logging.info(
                    f"Reverse tunnel requested: "
                    f"{remote_bind_address}:{remote_port} -> {local_host}:{local_port}"
                )
            except TypeError as e:
                logging.error(f"TypeError with request_tcp_forward: {e}")
                logging.info("Trying request_port_forward instead...")
                if hasattr(transport, "request_port_forward"):
                    # Inspect the arguments of request_port_forward
                    sig = inspect.signature(transport.request_port_forward)
                    if len(sig.parameters) == 3:
                        transport.request_port_forward(remote_bind_address, remote_port, local_host)
                        logging.info("Reverse tunnel requested using request_port_forward (3 args): "
                                     f"{remote_bind_address}:{remote_port} -> {local_host}:{local_port}")
                    elif len(sig.parameters) == 4:
                        transport.request_port_forward(local_host, local_port, remote_bind_address, remote_port)
                        logging.info("Reverse tunnel requested using request_port_forward (4 args): "
                                     f"{remote_bind_address}:{remote_port} -> {local_host}:{local_port}")
                    else:
                        logging.critical(f"Unexpected number of arguments for request_port_forward: {len(sig.parameters)}")
                        sys.exit(1)
                else:
                    logging.critical("request_port_forward also not found.")
                    sys.exit(1)

        elif hasattr(transport, "request_port_forward"):
            try:
                # Inspect the arguments of request_port_forward
                sig = inspect.signature(transport.request_port_forward)
                if len(sig.parameters) == 3:
                    transport.request_port_forward(remote_bind_address, remote_port, local_host)
                    logging.info("Reverse tunnel requested using request_port_forward (3 args): "
                                 f"{remote_bind_address}:{remote_port} -> {local_host}:{local_port}")
                elif len(sig.parameters) == 4:
                    transport.request_port_forward(local_host, local_port, remote_bind_address, remote_port)
                    logging.info("Reverse tunnel requested using request_port_forward (4 args): "
                                 f"{remote_bind_address}:{remote_port} -> {local_host}:{local_port}")
                else:
                    logging.critical(f"Unexpected number of arguments for request_port_forward: {len(sig.parameters)}")
                    sys.exit(1)
            except TypeError as e:
                 logging.error(f"TypeError with request_port_forward: {e}")
                 logging.critical("Both request_tcp_forward and request_port_forward failed.")
                 sys.exit(1)
        else:
            logging.critical(
                "SSH transport object does not have either 'request_tcp_forward' or 'request_port_forward' attribute. "
                "This indicates an incompatible Paramiko version or a problem with the SSH connection."
            )
            sys.exit(1)

        # Start listening on the local port
        local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        local_socket.bind((local_host, local_port))
        local_socket.listen(5)

        logging.info(f"Listening on {local_host}:{local_port}")

        while True:
            forward_local(local_port, local_host, local_port, transport)
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
    except Exception as e:
        logging.error(f"An error occurred: {e}")
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
