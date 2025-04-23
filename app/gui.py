import os
import subprocess
import threading
import time
import sys
import tkinter as tk


pipe_name = r'\\.\pipe\recordcam_pipe'
pipe_handler = None
manage_camera_process = None
GUI_window = None


# def read_output(stream, label):
#     for line in iter(stream.readline, b''):
#         print(f"[{label}] {line.decode().strip()}")
#     stream.close()

# Send a command to manage_camera.py - need to make this async so it doesn lock GUI up
def send_command(command):
    try:
        global manage_camera_process, pipe_handler, pipe_name

        if manage_camera_process is None or manage_camera_process.poll() is not None:  
            # There is no subprocess object OR the process is dead (.poll() returns None if running or the exit code if not)
            print("Starting manage_camera.py subprocess...")
            try:
                manage_camera_process = subprocess.Popen(
                    ["python", "-u", "manage_camera.py"],
                    # stdout=subprocess.PIPE,
                    # stderr=subprocess.PIPE,
                    # These redirect manage_camera.py's output back to this script
                    # so it could be processed programmatically here instead of printing to the terminal.
                    # not necessary yet and making debugging manage_camera.py difficult, comment out for now

                    # *ACTUALLY* - This was blocking the subprocess while it waited for control of the terminal (STDOUT)
                    # So re-enable them, but use a seperate thread(s) for their output:
                    #stdout=subprocess.PIPE,
                    #stderr=subprocess.PIPE,

                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )

                # Start threads to read subprocess output
                #threading.Thread(target=read_output, args=( manage_camera_process.stdout, "STDOUT"), daemon=True).start()
                #threading.Thread(target=read_output, args=( manage_camera_process.stderr, "STDERR"), daemon=True).start()
                
                print("Started manage_camera.py")
            except Exception as e:
                print(f"Failed to start manage_camera.py subprocess: {e}")

                time.sleep(2)
                return
        

        # !!!!!!! os.path.exists only works on linux / unix , so none of this will work !!!!!!!
        # Check the pipe exists, check 7 times with 1 seconds delays, in case manage_camera needs time to start up
        # print("Checking for manage_camera.py's pipe")
        # retries = 7
        # for attempt in range(retries):
        #     try:
        #         if not os.path.exists(pipe_name):
        #             print( f"Pipe {pipe_name} not found. Attempt {attempt + 1}/{retries}" )
        #             time.sleep(1)
        #         elif os.path.exists(pipe_name):
        #             print("pipe created so jump out")
        #             break
        #     except Exception as e:
        #         print(f"Retries exhausted - manage_camera.py has not created the pipe: {e}")
        #         return
        
        

        # Try to open the pipe
        if pipe_handler is None or pipe_handler.closed:       # (pipe_handler.closed is a built in boolean "read-only property" (aka. an "attribute"))
            retries = 5
            for attempt in range(retries):
                try:
                    pipe_handler = open(pipe_name, 'w')
                    print("Pipe opened and ready for writing.")
                    break  # exit the for loop
                except Exception as e:
                    print(f"Failed to open pipe (attempt {attempt+1}): {e}")
                    time.sleep(1)
            else:
                raise Exception(f"Failed to open the pipe after {retries} attempts.")
        
        # Try to send a message through the Pipe
        retries = 3
        for attempt in range(retries):
            try:
                pipe_handler.write(command + '\n')
                pipe_handler.flush()
                print(f"Command '{command}' sent to manage_camera.py")
                return  # exit the send_command function completly (not break !!)
            except Exception as e:
                print(f"Failed to send command (attempt {attempt+1}): {e}")
    
    except: # catch every type of exception
        print("Problem starting the camera process, finding the pipe, or sending a command")

# end function


# GUI functions:
def start_recording():
    send_command("start_record")
def stop_recording():
    send_command("stop_record")
def start_showing():
    send_command("show_stream")
def stop_showing():
    send_command("hide_stream")

def on_exit():
    print("GUI closed. Stopping subprocesses and closing pipe")
    # probably a good idea to notify the user too, just "shutting down..." as this may take a couple of seconds to gracefully shut down everything

    global manage_camera_process, pipe_handler, GUI_window
    
    # Send the exit command, if process is still running
    if manage_camera_process and manage_camera_process.poll() is None:  # again - None means running
        send_command("exit")  # no exception to catch here as already caught the exception inside the send_command
        print("Sent exit command to subprocess")
        for _ in range(3):
            print("Checking if subprocess exited")
            time.sleep(3)
            if manage_camera_process.poll() is not None:
                print("Subprocess terminated.")
                break # break from for loop (return would break from the whole function...)
        # end for
        # if manage_camera_process.poll() is None:  # again - None means running
        #     print("Failed to send the exit command after 3 attempts, force terminating subprocess...")
        #     manage_camera_process.terminate()
    else:
        print("No Subprocess created yet or all have been closed.")
    
    # Try to close the Pipe if it's still open
    if pipe_handler and not pipe_handler.closed:
        try:
            pipe_handler.close()
            if pipe_handler.closed:
                print("pipe closed!")
            else:
                print("pipe cant be closed!!!!!")

        except Exception as e:
            print(f"error closing the pipe: {e}")
    
    GUI_window.destroy() # End the GUI's main loop

# GUI setup
def gui_setup():

    print("setting up gui")

    global GUI_window
    GUI_window = tk.Tk()
    GUI_window.title("Camera Control")

    print("gui has been set up")

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
