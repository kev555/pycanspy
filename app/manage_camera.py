import cv2
import threading
import win32pipe
import win32file
import pywintypes

import time

pipe_name = r'\\.\pipe\recordcam_pipe'

# global controls
process_running = True
show_stream = False
recording = False
camera_in_use = False
exit_button_pressed = False

# these could be passed instaed of being global...
writer = None
cap = None
pipe_handler = None

def handle_commands():
    global show_stream, recording, writer, camera_in_use, process_running, exit_button_pressed, pipe_handler

    while process_running:
        pipe_handler = win32pipe.CreateNamedPipe(
            pipe_name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536,
            0,
            None
        )

        try:
            print("[SP:] Waiting for GUI to connect to pipe...")
            win32pipe.ConnectNamedPipe(pipe_handler, None)
            print("[SP:] GUI connected to pipe.")
        except pywintypes.error as e:
            print("problem with ConnectNamedPipe")
            break

        while process_running:
            try:
                print("[SP:] Should wait here for a command.")
                result, data = win32file.ReadFile(pipe_handler, 64 * 1024) # <- is this blocking or not?
                print("[SP:] Should not get here without getting a new command, command recieved?")
                
                cmd = data.decode().strip()
                print(f"[SP:] Received command: {cmd}")

                if cmd == "show_stream":
                    show_stream = True
                    camera_in_use = True  # Trun the camera loop on after setting things up here
                elif cmd == "hide_stream":
                    show_stream = False
                elif cmd == "start_record":
                    if writer is None:
                        fourcc = cv2.VideoWriter_fourcc(*'XVID')
                        writer = cv2.VideoWriter("output.avi", fourcc, 20.0, (640, 480))
                    recording=True
                    camera_in_use = True  # Trun the camera loop on after setting things up here
                elif cmd == "stop_record":
                    if writer:
                        writer.release()
                        writer=None
                    recording=False
                elif cmd == "exit":
                    print("[SP:] Exiting...")
                    exit_button_pressed = True  # i think more graceful to exit from the inside camera_control_and_loop, instead of just killing it from here
                    return # dont wait for the pipe_handler again
                cmd = "noting new"
            except pywintypes.error as e:
                print(f"[SP:] Error reading from pipe_handler: {e}")  # HUH?
                process_running = False
                return

def camera_control_and_loop():
    # runs once each time camera_in_use is triggered
    print("[SP:] camera_control_and_loop begining")
    global writer, camera_in_use, exit_button_pressed, process_running, cap
    
    # open webcam
    print("[SP:] Opening webcam.")
    cap=cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[SP:] Could not open webcam.")
        return
    else:
        print("[SP:] Opened webcam.")
    
    while camera_in_use:
        if exit_button_pressed:
            clean_camera()
            camera_in_use = False
            process_running = False # will force the _main_ while loop to exit and thus program end, must break camera_control_and_loop first
            return

        ret, frame = cap.read()  # read one frame constantly while camera in use
        if not ret:
            print("[SP:] could not read frame from camera")
            break

        if recording:
            writer.write(frame)
        
        if show_stream:
            cv2.imshow("Live", frame)
            if cv2.waitKey(1) == 27:
                break
        
        if not recording and not show_stream:   # camera not in use so close it to save resources
            clean_camera()
            camera_in_use = False
            break

# This camera_control_and_loop function will only run again if if camera_in_use wasn't turned off (see main)
# Next time camera_in_use turned on - a new cap object is generated at the top of camera_control_and_loop anyway

def clean_camera():
    print("[SP:] Cleaning up")
    global writer, cap
    
    # Try to release camera
    if cap:
        print("[SP:] cap exists, releasing")
        cap.release()

    if cap.isOpened():
        print("[SP:] cap still appears open after release!")
    else:
        print("[SP:] cap released")

    # Also try to destroy stream window
    cv2.destroyWindow("Live")
    cv2.destroyAllWindows()
    try:
        visible = cv2.getWindowProperty("Live", cv2.WND_PROP_VISIBLE)
        if visible < 1:
            print("[SP:] stream window destroyed!")
        else:
            print("[SP:] stream window still visible")
    except cv2.error:
        print("[SP:] stream window destroyed!! (no longer accessible)")
# End while loop


if __name__ == "__main__":
    threading.Thread(target=handle_commands, daemon=True).start() # <- Non-Blocking, thread to listen on pipe and relay commands
    while process_running:
        if camera_in_use:
            camera_control_and_loop()    # <- Blocking, camera must be turned off first or process_running loop can't end
        if exit_button_pressed:          # <- If exit pressed, process_running will also end, so kill the pipe here just befre ending
            print("[SP:] Attempting to safely disconnecting the pipe_handler")
            try:
                win32pipe.DisconnectNamedPipe(pipe_handler)
                print("[SP:] Pipe disconnected successfully")
            except pywintypes.error as e:
                print(f"[SP:] Failed to disconnect pipe: {e}")
            # Safely close the pipe handle
            try:
                win32file.CloseHandle(pipe_handler)
                print("[SP:] Pipe handle closed successfully")
            except pywintypes.error as e:
                print(f"[SP:] Failed to close pipe_handler handle: {e}")
            break

    print("[SP:] subprocess ended, exiting.")