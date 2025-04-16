import tkinter as tk
import subprocess
import threading
import time
import os
import signal
import cv2


recording_process = None
recording_duration = 350

def start_recording():
    global recording_process

    if recording_process is not None:
        print("Already recording.")
        return

    # Start the script
    recording_process = subprocess.Popen(
        ["python", "record_cam.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP  # Important for termination
    )
    print("Recording started.")

    # Start timer in background
    threading.Thread(target=auto_stop_after_delay, daemon=True).start()

def auto_stop_after_delay():
    time.sleep(recording_duration)
    stop_recording()

def stop_recording():
    global recording_process
    if recording_process is not None:
        try:
            # Send SIGTERM to process group
            os.kill(recording_process.pid, signal.CTRL_BREAK_EVENT)
            recording_process.wait(timeout=5)
            print("Recording stopped.")
        except Exception as e:
            print(f"Error stopping recording: {e}")
        finally:
            recording_process = None
    else:
        print("No recording to stop.")
        

def setup_gui():
    window = tk.Tk()
    window.title("Webcam Recorder")

    start_button = tk.Button(window, text="Start Record", command=start_recording)
    start_button.pack(pady=10)

    stop_button = tk.Button(window, text="Stop", command=stop_recording)
    stop_button.pack(pady=10)


    window.mainloop()

# Run GUI
setup_gui()