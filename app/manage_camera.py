import cv2
import threading
import socket
import time
import datetime
import os
import queue

process_running = True
show_stream = False
recording = False
camera_in_use = False
remote_viewing = False
exit_command = False

writer = None
webcam_obj = None

host = '127.0.0.1'  # or 'localhost'
port = 5000         # any free port
server_socket = None

script_directory = os.path.dirname(os.path.abspath(__file__))
output_subdirectory = "webcam_recordings"
output_dir = os.path.join(script_directory, output_subdirectory)
os.makedirs(output_dir, exist_ok=True)
clip_interval_secs = 5


def listen_connections():
    global show_stream, recording, writer, camera_in_use, process_running, exit_command
    global host, port, server_socket
    
    while process_running:                  # Socket initialization, listen for connection, then listen for command loop
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # = "make a socket object which will use the network stack (AF_INET), specifically TCP for transport (SOCK_STREAM), not UDP"
        server_socket.bind((host, port))    # bind to the socket
        server_socket.listen(1)             # listen to the socket, single connection; can be expanded
        print("[SP:] Waiting for client to connect to socket...\n")
        try:
            conn, addr = server_socket.accept()     # <- blocking, will wait here for a connection
        except Exception as e:
            print(f"Problem accepting connection: {e}")
            break
        print("[SP:] Client connected: ", conn, addr)
        
        new_thread = threading.Thread(target=listen_commands, name=f"Thread-ClientIP-{addr[0]}", args=(conn, addr)) 
        # Create a new thread for each connection, and name it by IP
        # there is multiple conn objects so can't use a global conn, just pass new one to thread each time with args=conn
        new_thread.start()

    print("[SP:] listen_connections finished")

def listen_commands(conn, addr):      # new thread each time to listen for commands on each connection socket obj (conn)
    global writer, camera_in_use, exit_command, process_running, webcam_obj
    global host, port, server_socket, show_stream, output_dir, clip_interval_secs
    while process_running:
        try:
            print("[SP:] Waiting here for a command...", conn)
            data = conn.recv(65536)         # <- blocking, recv = "receive", app will just hang here until a command or exit is recieved
            if not data:
                print("[SP:] Empty payload == connection closed by client")
                break
            cmd = data.decode().strip()     # print("UTF-8 decoded bytes:", cmd)
            print("[SP:] Command received:", cmd)
            if cmd == "show_stream":
                show_stream = True
                camera_in_use = True        # Turn the camera loop on after setting things up here
            elif cmd == "hide_stream":
                show_stream = False
            elif cmd == "start_record":     # as this function is threaded (asynchronous), these operations will not block cam_frame_loop
                recording=True              # now it will record on the next loop
                camera_in_use = True        # Turn the camera loop on after setting things up here
            elif cmd == "stop_record":
                recording=False             # don't release the cv writer here, causing problems, do it in loop
            elif cmd == "exit":
                graceful_socket_shutdown(conn)  # need to close the socket from here as each listen_commands thread has it's own non-global socket object
                exit_command = True             # gracefully exit from the inside cam_frame_loop, instead of just killing it from here
                return                          # break while loop so as not to wait for another command
            cmd = "blank"
        except ConnectionResetError:
            print("[SP:] Connection was closed/reset by client.")
            break
        except Exception as e:
            print(f"[SP:] Error reading from socket: {e}")
            break

    print("[SP:] listen_commands finished")


def cam_frame_loop():  # New webcam_obj etc generated upon each restart of this
    global writer, camera_in_use, exit_command, process_running, webcam_obj
    global host, port, conn, server_socket, show_stream, output_dir, clip_interval_secs

    print("[SP:] Opening webcam.")
    webcam_obj = cv2.VideoCapture(0, cv2.CAP_DSHOW) # CAP_DSHOW = windows direct show, may need to change for linux

    if not webcam_obj.isOpened():
        print("[SP:] Could not open webcam.")
        return
    else:
        print("[SP:] Opened webcam.")

    while camera_in_use:                # Runs as long as camera_in_use is true
        start_time = time.time()        # take the time before reading frame (+ other operations)
        if exit_command:
            print("[SP:] Exiting...")
            clean_camera()
            camera_in_use = False
            process_running = False     # will force the _main_ while loop to exit and thus program end, must break cam_frame_loop first
            return

        ret, frame = webcam_obj.read()  # read one frame each loop always, if ret is false = no frame available 
        if not ret:
            print("[SP:] could not read a frame from camera on this iteration")
            # break
            # dont break here. if the loop is attempting to read frames faster than they are being captured by the webcam this could cause issues
            # if the webcam driver or OpenCV doesn't buffer the frames in a way that makes them available for the extra reads 
            # ie "re-read previous frame if new one not available" - then you will get ret as False and the loop will exit
            # !!! Maybe good idea to: check advertised FPS of the camera, 
            # measure time taken to read a frame + do other processes in this loop,
            # wait for the difference of those times at the bottom, befre running the loop againa nd capturing an already captured frame 
            # saving processing power and data
            pass
            
        if show_stream:
            cv2.imshow("Live", frame)
            if cv2.waitKey(1) == 27:         # delay of 1 millisecond only. cv2.waitKey is mandatory it seems, not sure why...
                print("[SP:] ESC PRESSED!!")
                show_stream = False
                cv2.destroyWindow("Live")

        if recording:
            if writer is None:  # means new recording triggered - so create a new filename and 10-second segment
                output_file = os.path.join(output_dir, f"webcam_{time.strftime("%Y%m%d_%H%M%S")}.mp4") # ".mp4 = use mp4 container"  (best for web)
                fourcc = cv2.VideoWriter_fourcc(*'avc1')  # fourcc = "4 character codec", * = unpack operator, avc1 = H.264 -> is best for web, returns 32bit int codec ID
                writer = cv2.VideoWriter(output_file, fourcc, 20.0, (640, 480)) # must create a new cv2.VideoWriter each time, no way to update it
                end_time = time.time() + clip_interval_secs # unix time is in seconds so just add
            
            if end_time > time.time():
                writer.write(frame)
            else:
                writer.release()
                writer = None   # trigger the if above again to create a new filename

        if not recording:
            if writer is not None:  # when the recording is stopped release the writer
                writer.release()
                writer = None    #  set back to None, also explicitly dereferencing frees memory where the VideoWriter instance was stored
            
            if not show_stream:   # not recording + not showing screen = camera not in use so close webcam_obj to save resources
                clean_camera()
                camera_in_use = False
                break

    print("[SP:] cam_frame_loop finished")


def clean_camera():
    print("[SP:] Cleaning up")
    global host, port, conn, server_socket, writer, webcam_obj
    
    if webcam_obj:              # Try to release camera
        webcam_obj.release()
    if webcam_obj.isOpened():
        print("[SP:] webcam_obj still appears open after release!")

    cv2.destroyAllWindows()     # will close all if any exist, won't raise an error if none exist

    # check it's closing properly, if facing issues:
    # try:
    #     visible = cv2.getWindowProperty("Live", cv2.WND_PROP_VISIBLE)
    #     if visible < 1:
    #         print("[SP:] stream window destroyed!")
    #     else:
    #         print("[SP:] stream window still visible")
    # except cv2.error:
    #     print("[SP:] stream window destroyed!! (no longer accessible)")

    print("[SP:] clean_camera finished")


def graceful_socket_shutdown(conn):
    print("[SP:] Attempting to safely disconnecting the socket", conn)
    try:
        conn.shutdown(socket.SHUT_RDWR)  # Gracefully shut down both directions
        print("[SP:] Socket shutdown successfully")
    except OSError as e:
        print(f"[SP:] Failed to shutdown socket: {e}")
    except Exception as e:
        print(f"[SP:] Failed to shutdown socket!: {e}")
    try:                                # Now close the socket
        conn.close()
        print("[SP:] Socket closed successfully")
    except OSError as e:
        print(f"[SP:] Failed to close socket: {e}")


if __name__ == "__main__":
    threading.Thread(target=listen_connections, daemon=True).start()    # <- Non-Blocking, thread to listen on socket and relay the commands
    while process_running:
        if camera_in_use:
            cam_frame_loop()        # <- Blocking, camera must be turned off first or process_running loop can't end
        if exit_command:            # <- If exit pressed, process_running will also end, so kill the socket here just befre ending
            break
        time.sleep(2)               # massivly reduces CPU usage while camera not in use
    print("[SP:] Subprocess ended, exiting.")
    # is there any way process_running is true while camera in use and exit_command are false? this would get stuck if so ?????
