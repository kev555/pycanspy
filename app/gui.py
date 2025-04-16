import os
import subprocess
import time
import threading
import sys
import win32pipe
import win32file
import tkinter as tk


pipe_name = r'\\.\pipe\recordcam_pipe'
recording_process = None

# Function to send a command to manage_camera.py
# Start the subprocess only if it's not running already
# ie. the camera won't automatically start when the GUI starts, only when the user selets an option eg view video stream or record video stream
# So the GUI open and works smoothly at first

# def send_command(command):
#     try:
#         # Start the subprocess only if it's not running already
#         global recording_process
#         if recording_process is None:
#             print("[*] Starting manage_camera.py subprocess...")
#             recording_process = subprocess.Popen(
#                 ["python", "manage_camera.py"],
#                 stdout=subprocess.PIPE,
#                 stderr=subprocess.PIPE,
#                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
#             )
#             print("Started manage_camera.py")

#         # Now send the command to the pipe
#         with open(pipe_name, 'w') as pipe:
#             pipe.write(command + '\n')
#             pipe.flush()  # Make sure the command is sent

#         print(f"Command '{command}' sent to manage_camera.py")

#     except Exception as e:
#         print(f"[!] Failed to send command: {e}")

# However - the camera is not set up in time before the pipe command is sent, so change it:

# Function to send a command to manage_camera.py
def send_command(command):
    try:
        global recording_process
        if recording_process is None:
            print("[*] Starting manage_camera.py subprocess...")
            recording_process = subprocess.Popen(
                ["python", "manage_camera.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            print("Started manage_camera.py")

            time.sleep(3)  # Small delay to ensure the pipe is ready

        # Now send the command to the pipe
        retries = 3  # Retry a few times in case the pipe isn't ready
        for attempt in range(retries):
            try:
                with open(pipe_name, 'w') as pipe:
                    pipe.write(command + '\n')
                    pipe.flush()  # Make sure the command is sent
                print(f"Command '{command}' sent to manage_camera.py")
                return  # Successfully sent, exit the function
            except Exception as e:
                print(f"[!] Failed to send command (attempt {attempt+1}): {e}")
                time.sleep(1)  # Wait a moment and try again

    except Exception as e:
        print(f"[!] Failed to send command: {e}")




# GUI function to start recording
def start_recording():
    send_command("start_record")
    print("Recording started.")

# GUI function to stop recording
def stop_recording():
    send_command("stop_record")
    print("Recording stopped.")

# GUI function to show camera stream
def start_showing():
    send_command("show_stream")
    print("Camera stream started.")

# GUI function to hide camera stream
def stop_showing():
    send_command("hide_stream")
    print("Camera stream stopped.")

# GUI function to stop the subprocess and cleanup
def stop_process():
    send_command("exit")
    print("Exiting subprocess.")
    global recording_process
    if recording_process is not None:
        recording_process.terminate()
        recording_process = None
        print("Subprocess terminated.")

# GUI setup function
def gui_setup():

    window = tk.Tk()
    window.title("Camera Control")

    # Buttons
    record_button = tk.Button(window, text="Start Recording", command=start_recording)
    record_button.pack(pady=10)

    stop_button = tk.Button(window, text="Stop Recording", command=stop_recording)
    stop_button.pack(pady=10)

    show_button = tk.Button(window, text="Show Camera Stream", command=start_showing)
    show_button.pack(pady=10)

    hide_button = tk.Button(window, text="Hide Camera Stream", command=stop_showing)
    hide_button.pack(pady=10)

    quit_button = tk.Button(window, text="Quit", command=window.quit)
    quit_button.pack(pady=10)

    window.mainloop()

# Run GUI
if __name__ == "__main__":
    gui_setup()

    stop_process()
    print("GUI closed. Exiting...") 
    sys.exit(0)
