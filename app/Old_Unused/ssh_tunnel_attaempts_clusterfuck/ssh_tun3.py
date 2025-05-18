import paramiko
import socket
import threading
import sys
import time
import inspect  # Import the inspect module
import signal  # Import the signal module


local_socket = None
running = True  # Added global flag for Ctrl+C
stop_event = threading.Event()  # Use threading.Event


def forward_local(local_port, remote_host, remote_port, transport):
    """Handles the forwarding of a single connection."""
    global local_socket
    global running
    global stop_event
    try:
        sock, addr = local_socket.accept()
        print(f"Accepted connection from {addr[0]}:{addr[1]} on local port {local_port}")
        while running and not stop_event.is_set():  # Check both flags
            try:
                data = sock.recv(4096)
                if not data:
                    break
                transport.send(data)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error forwarding data: {e}")
                break
            try:
                data = transport.recv(4096)
                if not data:
                    break
                sock.send(data)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error forwarding data: {e}")
                break
        sock.close()

    except Exception as e:
        print(f"Error accepting connection on local port {local_port}: {e}")
        return

    channel = None
    try:
        channel = transport.open_channel("direct-tcpip", (remote_host, remote_port), sock.getpeername())
    except Exception as e:
        print(
            f"Could not connect to {remote_host}:{remote_port} from "
            f"local port {local_port}: {e}"
        )
        sock.close()
        return

    if channel is None:
        print(
            "Channel is None.  This likely means the remote SSH server rejected the connection."
        )
        sock.close()
        return

    sock.settimeout(5)
    channel.settimeout(5)


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
    global stop_event
    try:
        # Create an SSH client
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the SSH server
        print(f"Connecting to {ssh_user}@{ssh_host}:{ssh_port}")
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
                    print(
                        "Private key requires a passphrase.  Please provide the passphrase."
                    )
                    sys.exit(1)
                except paramiko.ssh_exception.SSHException as e:
                    print(f"Error reading private key: {e}")
                    sys.exit(1)
            else:
                print(
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
            print("SSH transport is not active.")
            sys.exit(1)
        transport.set_keepalive(60)

        # Assume request_port_forward
        if hasattr(transport, "request_port_forward"):
            # Inspect the arguments of request_port_forward
            sig = inspect.signature(transport.request_port_forward)
            if len(sig.parameters) == 3:
                transport.request_port_forward(
                    remote_bind_address, remote_port, local_host
                )
                print(
                    "Reverse tunnel requested using request_port_forward (3 args): "
                    f"{remote_bind_address}:{remote_port} -> {local_host}:{local_port}"
                )
            elif len(sig.parameters) == 4:
                transport.request_port_forward(
                    local_host, local_port, remote_bind_address, remote_port
                )
                print(
                    "Reverse tunnel requested using request_port_forward (4 args): "
                    f"{remote_bind_address}:{remote_port} -> {local_host}:{local_port}"
                )
            else:
                print(
                    f"Unexpected number of arguments for request_port_forward: {len(sig.parameters)}"
                )
                sys.exit(1)
        else:
            print(
                "SSH transport object does not have 'request_port_forward' attribute. "
                "This indicates an incompatible Paramiko version or a problem with the SSH connection."
            )
            sys.exit(1)

        # Start listening on the local port
        local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        local_socket.bind((local_host, local_port))
        local_socket.listen(5)

        print(f"Listening on {local_host}:{local_port}")

        while running and not stop_event.is_set():  # Main loop controlled by the running flag
            forward_local(local_port, local_host, local_port, transport)
            if not transport.is_active():
                print("SSH transport disconnected.  Exiting.")
                break
        if local_socket:
            local_socket.close()

    except paramiko.AuthenticationException:
        print("Authentication failed.")
        sys.exit(1)
    except paramiko.SSHException as ssh_exception:
        print(f"SSH error: {ssh_exception}")
        sys.exit(1)
    except socket.error as socket_error:
        print(f"Socket error: {socket_error}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass

        print("Connection closed.")


def handle_sigint(signal, frame):
    """Handles the SIGINT signal (Ctrl+C)."""
    global running
    global stop_event
    print("Ctrl+C caught.  Exiting...")
    running = False
    stop_event.set()  # set the stop event



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

    # Set the signal handler for SIGINT (Ctrl+C)
    signal.signal(signal.SIGINT, handle_sigint)

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
