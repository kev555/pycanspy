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
import numpy as np

# Control vars:
process_running = True
show_stream = False
recording = False
camera_in_use = False
server_viewing = False
exit_command = False

FPS = 1 / 5

# OpenCV objs
writer = None
webcam_obj = None

# Saving video
clip_interval_secs = 5
# make sure director for saving videos clips exists:
script_directory = os.path.dirname(os.path.abspath(__file__))
output_subdirectory = "webcam_recordings"
output_dir = os.path.join(script_directory, output_subdirectory)
os.makedirs(output_dir, exist_ok=True)

# Network
local_host = '127.0.0.1'        # For listening to GUI commands
local_port = 5000               # For listening to GUI commands
#server_host = '146.190.96.130' # VPS's public IP
server_host = '127.0.0.1'       # Use this if running server_process.py locally for testing
server_recieve_port = 5001      # VPS display port (1705) is different from recieve port (5001)
server_socket = None
client_socket = None

frame_queue = queue.Queue(maxsize=300)
# queue.Queue(maxsize=300) = 300 fames max
# if frames are being produced MUCH faster than being consumed the Queue will fill up 
# "except queue.Full" be raised when trying to .put another frame on the queue (in cam_frame_loop)
# although this won't fail it will cause frames to be dropped from the remote viewing
# with 300 frames Queue and ~30 fps camera == 10 delay before starting to drop frames

# *IMPORTANT
# "two (or more) threads can safely read from the same queue.Queue in Python"
# HOWEVER this is not as it seems:
# ✅ Multiple threads can get() from the queue safely
# ✅ Multiple threads can put() into the queue safely
# ✅ You can even mix readers and writers across many threads without race conditions
# queue.Queue is built for multi-threaded use
# !The queue is designed for work-sharing, not broadcasting
# So if Thread A reads an item, it’s gone — Thread B won’t see it.
# So this cannot be used to read the frame once and grab it by mulitple peers

# Would need to use multiple queues or a subscriber / publisher method/library/server


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
        max_connect_retries = 1                         # try 5 times, incase peer is busy
        for attempt in range(max_connect_retries):
            try:
                client_socket.connect((server_host, server_recieve_port))     # ConnectionRefusedError if not working
                return client_socket
            except Exception as e:
                print(f"Connection attempt {attempt+1} failed: {e}")
                time.sleep(1)
        else:
            raise Exception( f"Failed to connect after {max_connect_retries} attempts.")

# VPS socket listener thread function 
def VPS_master_socket_reverse_listener():
    global client_socket
    global show_stream, recording, writer, camera_in_use, process_running, exit_command
    global local_host, local_port, server_socket
    
    try:
        client_socket = createSocket(client_socket)                 # Create socket, will return a newly created / re-created socket if client_socket is None
        connectSocket(client_socket)                                # Connect socket, will directly modify the returned client_socket, no need to return + reassign
        # these shuldnt be done differently, it's confusingg....
        # change above:
        # return socket.socket(socket.AF_INET, socket.SOCK_STREAM) to:
        # client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # no need to bind or listen here, the VPS does that, just pass the socket ti a thread
    
        threading.Thread(target=listen_commands_on_master_socket, name=f"Thread-ClientIP-{999}", args=(client_socket, 9999)).start()
    except Exception as e:
        print("Caught Exceptionnnnn44444:", e, "Original cause:", e.__cause__)

# local socket listener thread function 
def local_master_socket_listener():
    global show_stream, recording, writer, camera_in_use, process_running, exit_command
    global local_host, local_port, server_socket
    
    # Socket initialization - this is the permenant gateway socket for all connections
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # = "make a socket object which will use the network stack (AF_INET), specifically TCP for transport (SOCK_STREAM), not UDP"
    server_socket.bind((local_host, local_port))    # bind to the socket
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
        time.sleep(1)
        
        threading.Thread(target=listen_commands_on_master_socket, name=f"Thread-ClientIP-{addr[0]}", args=(conn, addr)).start()
        # Create a new thread for each connection, and name it by IP
        # there is multiple conn objects so can't use a global, just pass new one to thread each time with args=conn

    print("[SP:] listen_connections finished")

def listen_commands_on_master_socket(conn, addr):      # new thread each time to listen for commands on each connection socket obj (conn)
    # Each of these threads will listen to a master socket (eithr local or VPS from now), for commands
    global writer, camera_in_use, exit_command, process_running, webcam_obj, recording
    global local_host, local_port, server_socket, show_stream, output_dir, clip_interval_secs
    global server_viewing

    stop_send_frames_to_VPS_event_obj = threading.Event()
    
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
                # new sub-thread each time VPS requests frames over the VPS-master-socket obj ("conn"), pass the thread the socket with args=conn
                # send frames directly back over this TCP connection, TCP is duplex, no need to create a new socket
                if stop_send_frames_to_VPS_event_obj.is_set():
                    stop_send_frames_to_VPS_event_obj.clear()
                VPS_send_thread = threading.Thread(target=send_frames_to_VPS, name=f"VPS_Send_Thread", args=(conn,stop_send_frames_to_VPS_event_obj,))
                VPS_send_thread.start()
                server_viewing=True
                # camera_in_use = True # not necessary yet, until i want to be able to trigger streaming ENTIRELY from remote VPS
            elif cmd == "stop_server_view":
                # just kill the VPS thread, this won't kill the socket so the thread can just be remade and passed the socket refrence again, efficent
                # Python threads can’t be forcefully killed from the outside in a safe, built-in way
                # must signal the thread with an Event to stop, and have the thread check for that signal regularly
                stop_send_frames_to_VPS_event_obj.set()
                # VPS_send_thread.join() 
                # use this if want to pause this main thread until that one finishes exiting, 
                # but that thread is very simple so no real need, it should end very quickly
                server_viewing=False
            elif cmd == "exit":
                graceful_socket_shutdown(conn)  # need to close the socket from here as each listen_commands_on_master_socket thread has it's own non-global socket object
                exit_command = True             # gracefully exit from the inside cam_frame_loop, instead of just killing it from here
                return                          # break while loop so as not to wait for another command
            cmd = "blank"
        except ConnectionResetError:
            print("[SP:] Connection was closed/reset by client.")
            break
        except Exception as e:
            print(f"[SP:] Error reading from socket: {e}")
            break

    print("[SP:] listen_commands_on_master_socket finished")


# Send frames to the VPS
def send_frames_to_VPS(conn, stop_send_frames_to_VPS_event_obj):

    while not stop_send_frames_to_VPS_event_obj.is_set():
        try:
            frame = frame_queue.get(timeout=1)                  # Get frame from queue, with timeout of 1 is enough?
            success, encoded_frame = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50]) # encode it now, before transmitting!!
            if not success:
                raise RuntimeError("Failed to encode frame")
            
            # Serialize the jpg frame into bytes:
            # frame_bytes = pickle.dumps(encoded_frame)
            # NO, Just use .tobytes(), pickle is unnecessary
            frame_bytes = encoded_frame.tobytes()
            
            # Send a description of the size of the frame_bytes to be transmitted
            # Use an "I" struct which is unsigned int (4 bytes)
            # Use type ">" for big-endian (or "!" for "network byte order" (TCP/IP standard), also big endian)
            frame_size_desc = struct.pack(">I", len(frame_bytes))  
            
            conn.sendall(frame_size_desc + frame_bytes)      
            # Send the first 4 bytes notifying the size of the frame data, then the frame data itslef
            # sendall() ensures that all the data you want to send is eventually transmitted, 
            # even if it has to be broken into multiple TCP packets, TCP will guarantee ordered delivery


            print("[SP:] Sent 1 frame to the VPS")

        except queue.Empty:
            print("[SP:] No frame in queue, continue to next iteration")
            continue # No frame in queue, continue to next iteration
        except Exception as e:
            print(f"Error sending frame: {e}")
            break  # Exit thread on error.  Important to prevent it from trying to send if the connection is broken.


def cam_frame_loop():  # New webcam_obj etc generated upon each restart of this
    global writer, camera_in_use, exit_command, process_running, webcam_obj, recording
    global local_host, local_port, conn, server_socket, show_stream, output_dir, clip_interval_secs
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
        #start_time = time.time()        # take the time before reading frame (+ other operations)
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
            print("sent a frame to the queue")
            try:
                frame_queue.put(frame, block=False)     # put frame in queue
            except queue.Full:
                print("Frame queue is full (or blocked?) - A frame was dropped")
                pass                                    # pass = no action needed placeholder
            # frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            # frame_queue.put(frame)
        
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
        
        time.sleep(FPS) # leave it at 5 frames per second so as not to exhaust VPS resources during testing
    
    # end camera_in_use
    print("[SP:] cam_frame_loop finished")


def clean_camera():
    print("[SP:] Cleaning up")
    global local_host, local_port, conn, server_socket, writer, webcam_obj
    
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
    # local socket thread:
    threading.Thread(target=local_master_socket_listener, daemon=True).start()
    # VPS socket thread:
    threading.Thread(target=VPS_master_socket_reverse_listener, daemon=True).start()
    
    while process_running:
        if camera_in_use:
            cam_frame_loop()        # <- Blocking, camera must be turned off first or process_running loop can't end
        if exit_command:            # <- If exit pressed, process_running will also end, so kill the socket here just befre ending
            break
        time.sleep(2)               # massivly reduces CPU usage while camera not in use
    print("[SP:] Subprocess ended, exiting.")
    # is there any way process_running is true while camera in use and exit_command are false? this would get stuck if so ?????
