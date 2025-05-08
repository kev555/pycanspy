import subprocess
import time
import sys
import tkinter as tk

import socket

manage_camera_process = None
GUI_window = None

# socket stuff
host = '127.0.0.1'  # or 'localhost'
port = 5000         # any free port
client_socket = None

# Send a command to manage_camera.py - need to make this async so it doesn lock GUI up
def send_command(command):
    global client_socket
    global manage_camera_process 
    global host, port

    try:
        # Start set up Subprocess
        if manage_camera_process is None or manage_camera_process.poll() is not None:  
            # There is no subprocess object OR the process is dead (.poll() returns None if running or the exit code if not)
            print("Starting manage_camera.py subprocess...")
            try:
                manage_camera_process = subprocess.Popen(  # spin off a new process, no waiting for confirmation that it started successfully or anything
                    ["python", "-u", "manage_camera.py"],
                    #stdout=subprocess.PIPE,
                    #stderr=subprocess.PIPE,
                    #creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    # tells operating system to groups manage_camera.py and any processes it subsequently spawns. 
                    # helps to terminate all subprocess - spawned processes once the subprocess is killed.. apparently 
                    # (not clear if this works well on windows or if subprocess_object.kill() even triggers what CREATE_NEW_PROCESS_GROUP sets...?)
                )
                print("Started manage_camera.py")
            except Exception as e:
                print(f"Failed to start manage_camera.py subprocess: {e}")
                time.sleep(1)
                return
        # Finish set up Subprocess
        
        # os.path.exists was a pre check also here previously, but it only works on linux / unix , not windows, so just try to open the pipe directly

        # create a socket object (does not connect to anything or open a connection yet)
        if client_socket is None:                                               # socket doesnt exist
            print("Creating socket...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # try to create it
        
        # Sometimes the client_socket exists but has been "closed".
        # Closing a socket with .close():
        # Does NOT destroy the Python object in memory.
        # DOES release the OS-level file descriptor,
        # check it with :
        if client_socket.fileno() == -1:
            print("Socket was closed... creating a new one...")                 # a closed socket is a dead socket, need to create a new one
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        if client_socket is None or client_socket.fileno() == -1:               # check if opened now
            print ("Could not create a socket")
            return
        else:
            print("Socket object created")

        # Connect to server socket if not already connected
        # make this a function - soccet_connect or something:
        max_connect_retries = 5
        try:
            client_socket.getpeername()             # client_socket.getpeername() attempts to return the address of the remote socket, raises OSError if socket not connected
            print("Socket is already connected.")
        except OSError:                             # Not connected, attempt connection
            for attempt in range(max_connect_retries):
                try:
                    client_socket.connect((host, port)) # ConnectionRefusedError if not working
                    print(f"Connected to socket on attempt {attempt+1}")
                    # try:
                    #     print("getsockname() from guiiiiiiiii:", client_socket.getsockname())
                    # except Exception as e:
                    #     print(f"guiiiiiiiii {e}")
                    break
                except Exception as e:
                    print(f"Connection attempt {attempt+1} failed: {e}")
                    time.sleep(1)
            else:
                raise Exception(
                    f"Failed to connect after {max_connect_retries} attempts.")
        
        # Try to send the command through socket
        max_send_retries = 3
        for attempt in range(max_send_retries):
            try:
                client_socket.sendall((command + '\n').encode())
                #print(f"Command '{command}' sent to subprocess")
                break
            except Exception as e:
                print(f"Send attempt {attempt+1} failed: {e}")
                time.sleep(1)
        else:
            raise Exception(
                f"Failed to send command after {max_send_retries} attempts.")

    except:  # catch every type of exception
        print("Problem starting the camera process, finding the socket, or sending a command")

# GUI functions:
def start_recording():
    send_command("start_record")
def stop_recording():
    send_command("stop_record")
def start_showing():
    send_command("show_stream")  # € to see raw bytes
def stop_showing():
    send_command("hide_stream")
def start_server_view():
    send_command("start_server_view")


def on_exit(): # change this name to do_exit
    print("GUI closed. Stopping subprocesses and closing socket")
    # probably a good idea to notify the user too, just "shutting down..." as this may take a couple of seconds to gracefully shut down everything

    global manage_camera_process, client_socket, GUI_window
    
    # Send the exit command, if process is still running
    if manage_camera_process and manage_camera_process.poll() is None:  # again - None means running
        send_command("exit")  # no exception to catch here as already caught the exception inside the send_command
        print("Sent exit command to subprocess")
        for _ in range(3):
            print("Checking if subprocess exited")
            time.sleep(1)
            if manage_camera_process.poll() is not None:
                print("Subprocess terminated.")
                break # break from for loop (return would break from the whole function...)
            else:
                print ("couldn't close sub process, trying again")
        if manage_camera_process.poll() is  None: # Still running after 5 seconds - kill manually!
            print("Subprocess didn't exit by itself, killing manually")
            manage_camera_process.kill()

    else:
        print("No Subprocess created yet or all have been closed.")
    
    
    # Try to close the socket if it's still open
    if client_socket and not client_socket.fileno() == -1: # "client_socket exitis but is not closed"
        print("huhh5555", client_socket)
        try:
            client_socket.shutdown(socket.SHUT_RDWR)  # Gracefully shut down both directions
            if client_socket.fileno() == -1:
                print("socket closed!")
            else:
                print("socket can't be closed, perhaps already closed by subprocess")
        except Exception as e:
            print(f"error closing the socket: {e}")

    GUI_window.destroy() # End the GUI's main loop

# GUI setup
def gui_setup():

    #print("setting up gui")

    global GUI_window
    GUI_window = tk.Tk()
    GUI_window.title("Camera Control")

    #print("gui has been set up")

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

    quit_button = tk.Button(GUI_window, text="Quit", command=on_exit)
    quit_button.pack(pady=10)

    # Also run the exit function when user clicks the [X] button
    GUI_window.protocol("WM_DELETE_WINDOW", on_exit)

    # Now i've covered both way the program can exit - "Quit" button and standard X button
    # so no need to run on_exit() again in the main loop, right?

    GUI_window.mainloop()

def main():
    gui_setup()
    # on_exit()             # no need for this here again

    print("Clean up complete, terminating main process")
    sys.exit(0)             # Terminate the process, 0 = no errors

# Run GUI
if __name__ == "__main__":
    main()
