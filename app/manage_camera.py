import threading
import socket
import time
import datetime
import os
import queue
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
import cv2
import pickle
import struct
import sys


process_running = True
show_stream = False
recording = False
camera_in_use = False
server_viewing = False
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

frame_queue = queue.Queue(maxsize=3000)
# queue.Queue(maxsize=200) = 200 fames max
# if frames are being produced MUCH faster than being consumed the Queue will fill up 
# "except queue.Full" be raised when trying to .put another frame on the queue (in cam_frame_loop)
# although this won't fail it will cause frames to be dropped from the remote viewing
# with 300 frames Queue and ~30 fps camera == 10 delay before starting to drop frames

def listen_connections():
    global show_stream, recording, writer, camera_in_use, process_running, exit_command
    global host, port, server_socket
    
    # Socket initialization - this is the permenant gateway socket for all connections
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
    # = "make a socket object which will use the network stack (AF_INET), specifically TCP for transport (SOCK_STREAM), not UDP"
    server_socket.bind((host, port))    # bind to the socket
    server_socket.listen(1)             # listen to the socket, single connection; can be expanded
    
    while process_running:        # listen for new connections, creating new sockets for each      
        print("[SP:] Waiting for a new client to connect to the socket...")
        try:
            conn, addr = server_socket.accept()     # <- blocking, listen for new connection attempted on this master socket, 
                                                    # then generate a new socket "conn" and link the connection request to that instead,
                                                    # then continue listeing on the master socket here, rinse and repeat
        except Exception as e:
            print(f"Problem accepting connection: {e}")
            break
        print("[SP:] Client connected: ", conn, addr)
        
        new_thread = threading.Thread(target=listen_commands, name=f"Thread-ClientIP-{addr[0]}", args=(conn, addr)) 
        # Create a new thread for each connection, and name it by IP
        # there is multiple conn objects so can't use a global, just pass new one to thread each time with args=conn
        new_thread.start()

    print("[SP:] listen_connections finished")

def listen_commands(conn, addr):      # new thread each time to listen for commands on each connection socket obj (conn)
    global writer, camera_in_use, exit_command, process_running, webcam_obj
    global host, port, server_socket, show_stream, output_dir, clip_interval_secs
    global server_viewing
    while process_running:
        try:
            print("[SP:] Waiting here for a command...")
            data = conn.recv(65536)     #   65536 bytes overkill    # <- blocking, recv = "receive", app will just hang here until a command or exit is recieved
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
            elif cmd == "start_server_view":      
                # additional new sub-thread each time each remote connection socket obj (conn)
                # send over the same (conn) TCP connection, (TCP is duplex), no need to creat a new socket / TCP connection
                # two (or more) threads can safely read from the same queue.Queue in Python
                # there is multiple conn objects so can't use a global conn, just pass new one to thread each time with args=conn

                print("[SP:] send_frame_server, conn obj:", conn)
                new_sub_thread = threading.Thread(target=send_frame_server, name=f"Sub-Thread-ClientIP-{addr[0]}", args=(conn,))
                new_sub_thread.start()
                server_viewing=True
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


def send_frame_server(conn):
    print("[SP:] send_frame_server, conn obj:", conn)
    while server_viewing:
        try:
            frame = frame_queue.get(timeout=1)                  # Get frame from queue, with timeout
            print("raw: ", sys.getsizeof(frame))                # Size of frame in bytes: 921799 !!!!!!?
            success, encoded_frame = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50]) # encode it now, before transmitting!!
            if not success:
                raise RuntimeError("Failed to encode frame")
            print("encoded: ", sys.getsizeof(encoded_frame))    # Size of frame in bytes: 16296 ! -> Much better for network transmission!
            
            frame_bytes = pickle.dumps(encoded_frame)           
            # Serialize the frame into bytes
            frame_size_desc = struct.pack(">I", len(frame_bytes))      
            # Send a describtion of the size of the frame_bytes to be transmitted 
            # Use an ">I" struct: > = big-endian (TCP/IP standard), I = unsigned int (4 bytes)
            
            conn.sendall(frame_size_desc + frame_bytes)      
            # Send the first 4 bytes notifying the size of the frame data, then the frame data itslef
            # sendall() ensures that all the data you want to send is eventually transmitted, 
            # even if it has to be broken into multiple TCP packets, TCP will guarantee ordered delivery

        except queue.Empty:
            print("[SP:] No frame in queue, continue to next iteration")
            continue # No frame in queue, continue to next iteration
        except Exception as e:
            print(f"Error sending frame: {e}")
            break  # Exit thread on error.  Important to prevent it from trying to send if the connection is broken.


def cam_frame_loop():  # New webcam_obj etc generated upon each restart of this
    global writer, camera_in_use, exit_command, process_running, webcam_obj
    global host, port, conn, server_socket, show_stream, output_dir, clip_interval_secs
    global frame_queue

    print("[SP:] Opening webcam.")
    webcam_obj = cv2.VideoCapture(0) 
    if not webcam_obj.isOpened():
        print("[SP:] Could not open webcam.")
        return
    else:
        print("[SP:] Opened webcam.")

    # camera_fps = webcam_obj.get(cv2.CAP_PROP_FPS) # was going to sync frames manually..... see note

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
            pass

        if show_stream:
            cv2.imshow("Live", frame)
            if cv2.waitKey(1) == 27:         # delay of 1 millisecond only. cv2.waitKey is mandatory it seems, not sure why...
                print("[SP:] ESC PRESSED!!")
                show_stream = False
                cv2.destroyWindow("Live")
        
        if server_viewing: # Obviously not going to try to process and send the frames here, send them to a queue, then use a thread to work off the queue
            try:
                frame_queue.put(frame, block=False)     # put frame in queue
            except queue.Full:
                print("Frame queue is full (or blocked?) - A frame was dropped")
                pass                                    # pass = no action needed placeholder
        
        if not server_viewing:
            # kill the remote viewing thread .. ?
            pass

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
    
    # end camera_in_use
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
