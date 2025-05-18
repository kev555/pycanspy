import paramiko
import time
import socket

REMOTE_HOST = '146.190.96.130'
REMOTE_PORT = 5678
LOCAL_HOST = 'localhost'
LOCAL_PORT = 5000
SSH_USERNAME = 'kev'
SSH_PASSWORD = 'Ap0llo###'

def establish_reverse_tunnel(remote_host, remote_port, local_host, local_port, username, password):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        client.connect(remote_host, port=22, username=username, password=password)
        print(f"SSH connection established to {remote_host}")

        transport = client.get_transport()
        transport.request_port_forward(int(remote_port), local_host, int(local_port))
        print(f"Reverse tunnel established: {remote_host}:{remote_port} -> {local_host}:{local_port}")

        while True:
            time.sleep(1)

    except paramiko.AuthenticationException:
        print("Authentication failed.")
    except paramiko.SSHException as e:
        print(f"Could not establish SSH connection: {e}")
    except socket.error as e:
        print(f"Socket error: {e}")
    finally:
        try:
            client.close()
            print("SSH connection closed.")
        except:
            pass

if __name__ == "__main__":
    establish_reverse_tunnel(REMOTE_HOST, REMOTE_PORT, LOCAL_HOST, LOCAL_PORT, SSH_USERNAME, SSH_PASSWORD)