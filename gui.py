import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
import os
import time

# To List all servvices INCLUDING stopped ones in wondwos cli use:
# wmic service get name,displayname,state | sort

# Global variable to hold the subprocess for the recording
recording_process = None

# Function to start the service (which records for 10 seconds)
def start_recording():
    global recording_process
    try:
        # Running the service script which will start and stop recording automatically
        recording_process = subprocess.Popen([sys.executable, "my_service.py"])
        messagebox.showinfo("Recording", "Recording started. It will stop automatically after 10 seconds.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to start recording: {str(e)}")

# Function to stop the recording manually
def stop_recording_manually():
    global recording_process
    if recording_process:
        recording_process.terminate()  # Terminate the recording process
        recording_process.wait()  # Ensure it fully terminates
        messagebox.showinfo("Recording", "Recording stopped manually.")
    else:
        messagebox.showwarning("No Recording", "No recording is currently running.")

# Create the main window
root = tk.Tk()
root.title("Webcam Recorder")

# Add a "Record" button
record_button = tk.Button(root, text="Start Recording", command=start_recording)
record_button.pack(pady=20)

# Add a "Stop Recording" button
stop_button = tk.Button(root, text="Stop Recording", command=stop_recording_manually)
stop_button.pack(pady=20)

# Start the GUI
root.mainloop()
