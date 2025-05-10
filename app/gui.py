import subprocess
import time
import sys
import tkinter as tk
import socket

GUI_window = None
manage_camera_process = None

# socket stuff
host = '127.0.0.1'  # or 'localhost'
port = 5000         # any free port
client_socket = None

# Setup the subprocess manage_camera.py
def makeaSubprocess():
    try:
        return subprocess.Popen(["python", "-u", "manage_camera.py"], ) # try make subprocess
    except Exception as e:
        raise Exception("Failed to start manage_camera.py subprocess") from e

# Create / re-create socket. If .close()'d the client_socket object reamins but the OS-level file descriptor is released (dead socket object)
def createSocket(client_socket):
    try:
        if client_socket is None:                                          # socket doesnt exist
            return socket.socket(socket.AF_INET, socket.SOCK_STREAM)       # create a socket object (does not connect to anything or open a connection yet)
        elif client_socket.fileno() == -1:                                 # exists but closed file descriptor
            return socket.socket(socket.AF_INET, socket.SOCK_STREAM)       # can't be reopend must create new one
        else:
            return client_socket                                           # socket exists and is open, so just return it
    except OSError as e:                                                   # socket creation error will raise OSError
            raise

# Connect to server socket if not already connected:
def connectSocket(client_socket):
    try:
        client_socket.getpeername()                     # retruns address of remote socket if connected, raises OSError not connected
    except OSError:                                     # not connected, attempt to connect
        max_connect_retries = 5                         # try 5 times, incase peer is busy
        for attempt in range(max_connect_retries):
            try:
                client_socket.connect((host, port))     # ConnectionRefusedError if not working
                return client_socket
            except Exception as e:
                print(f"Connection attempt {attempt+1} failed: {e}")
                time.sleep(1)
        else:
            raise Exception( f"Failed to connect after {max_connect_retries} attempts.")


def send_command(command):
    global client_socket
    global manage_camera_process

    try:
        if manage_camera_process is None or manage_camera_process.poll() is not None:   # If no subprocess yet OR it's dead (.poll() returns None if running, exit code if dead)
            manage_camera_process = makeaSubprocess()
        
        client_socket = createSocket(client_socket)                 # Create socket, will return a new created / re-created socket if client_socket is None
        connectSocket(client_socket)                                # Connect socket, will directly modify the current client_socket

        # Send command through socket:
        max_send_retries = 3
        for attempt in range(max_send_retries):
            try:
                client_socket.sendall((command + '\n').encode())    # this could block GUI if network congestion or reciever OS buffer full, needs to be async
                break
            except Exception as e:
                print(f"Send attempt {attempt+1} failed: {e}")
                time.sleep(1)
        else:
            raise Exception(
                f"Failed to send command after {max_send_retries} attempts.")

    except Exception as e:
        print("Caught Exception:", e, "Original cause:", e.__cause__)
        


def do_exit():
    global manage_camera_process, client_socket, GUI_window

    GUI_window.destroy()                                                # destroy the window first for better UI expireence

    # Send the exit command, if subprocess is still running:
    if manage_camera_process and manage_camera_process.poll() is None:  # None means running
        send_command("exit")                                            # already caught the exception inside send_command()
        for _ in range(3):
            print("Checking if subprocess exited")
            time.sleep(1)
            if manage_camera_process.poll() is not None:
                print("Subprocess terminated.")
                break                                                   # just break from for loop
        if manage_camera_process.poll() is  None:                       # still running? - kill manually
            print("Subprocess didn't exit, killing manually")
            manage_camera_process.kill()
    else:
        print("No Subprocess created yet or all have been closed.")
    
    # Try to close the socket, if it's still open:
    if client_socket and not client_socket.fileno() == -1:              # == "client_socket exists but is not closed"
        try:
            client_socket.shutdown(socket.SHUT_RDWR)                    # Gracefully shut down both directions
            if client_socket.fileno() == -1:
                print("socket closed!")
            else:
                print("socket can't be closed, perhaps already closed by subprocess")
        except Exception as e:
            print(f"error closing the socket: {e}")


# GUI functions:
def start_recording():
    send_command("start_record")
def stop_recording():
    send_command("stop_record")
def start_showing():
    send_command("show_stream")
def stop_showing():
    send_command("hide_stream")
def start_server_view():
    send_command("start_server_view")

# GUI setup
def gui_setup():
    global GUI_window
    GUI_window = tk.Tk()
    GUI_window.title("Camera Control")

    # Buttons
    record_button = tk.Button(
        GUI_window, text="Start Recording", command=start_recording)
    record_button.pack(pady=10)

    stop_button = tk.Button(
        GUI_window, text="Stop Recording", command=stop_recording)
    stop_button.pack(pady=10)

    show_button = tk.Button(
        GUI_window, text="Show Camera Stream", command=start_showing)
    show_button.pack(pady=10)

    hide_button = tk.Button(
        GUI_window, text="Hide Camera Stream", command=stop_showing)
    hide_button.pack(pady=10)

    hide_button = tk.Button(
        GUI_window, text="View On Server", command=start_server_view)
    hide_button.pack(pady=10)

    quit_button = tk.Button(GUI_window, text="Quit", command=do_exit)
    quit_button.pack(pady=10)

    GUI_window.protocol("WM_DELETE_WINDOW", do_exit) # Also run the exit function when user clicks the [X] button

    GUI_window.mainloop()

def main():
    gui_setup()

    print("Clean up complete, terminating main process")
    sys.exit(0)             # Terminate the process, 0 = no errors

# Run GUI
if __name__ == "__main__":
    main()
