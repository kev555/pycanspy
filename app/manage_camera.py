import threading
import socket
import time
import os
import queue
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
import cv2
import struct

# Control vars:
process_running = True
show_stream = False
recording = False
camera_in_use = False
server_viewing = False
exit_command = False
FPS = 1 / 5  # leave it at 5 frames per second so as not to exhaust VPS resources during testing
clip_interval_secs = 5

# OpenCV Objs:
writer = None
webcam_obj = None

# Make sure directory for saving videos clips exists:
script_directory = os.path.dirname(os.path.abspath(__file__))
output_subdirectory = "webcam_recordings"
output_dir = os.path.join(script_directory, output_subdirectory)
os.makedirs(output_dir, exist_ok=True)

# Network:
local_host = '127.0.0.1'        # For listening to GUI commands
local_port = 5000               # For listening to GUI commands
#server_host = '146.190.96.130' # VPS's public IP
server_host = '127.0.0.1'       # Use this if running server_process.py locally for testing
server_recieve_port = 5001      # VPS's display port (1705) is different from recieve port (5001)
local_master_socket = None
VPS_socket = None

frame_queue = queue.Queue(maxsize=100)

# Creates / re-creates socket.
# depending if socket doesnt exist yet or exists but has closed file descriptor
# If the temp_socket object has been .close()'d it will still exist,
# but the OS-level file descriptor is released (== a dead socket object)
# dead socket can't be reopend, must create new one
def createLocalSocket(temp_socket):
    try:
        if temp_socket is None or temp_socket.fileno() == -1: 
            return socket.socket(socket.AF_INET, socket.SOCK_STREAM)     # retrun a new socket object (does not connect to anything or open a connection yet)
        else:
            return temp_socket                                           # socket exists and is open, so just return it
    except OSError as e:                                                 # socket creation error will raise OSError
            raise

# Connect to server socket if not already connected
def connectToExternalSocket(temp_socket):
    try:
        temp_socket.getpeername()                       # retruns address of remote socket if connected, raises OSError not connected
    except OSError:                                     # not connected, attempt to connect
        max_connect_retries = 3                         # try 3 times, incase the peer is busy
        for attempt in range(max_connect_retries):
            try:
                temp_socket.connect((server_host, server_recieve_port))
                return temp_socket
            except Exception as e:
                print(f"Connection attempt {attempt+1} failed: {e}")
                time.sleep(1)
        else:
            raise Exception( f"Failed to connect after {max_connect_retries} attempts.")

# VPS socket listener thread function
# no need to bind or listen here, the VPS does that, just pass the socket to command listener thread
def VPS_master_socket_reverse_listener():
    global VPS_socket
    try:
        VPS_socket = createLocalSocket(VPS_socket)
        VPS_socket = connectToExternalSocket(VPS_socket)
        threading.Thread(target=listen_commands_on_socket_thread, name="VPS_master_socket_thread", args=(VPS_socket, 0)).start()
    except Exception as e:
        print("Caught Exception in VPS_master_socket_reverse_listener:", e, "Original cause:", e.__cause__) # e.__cause__ reads previous exception?

# local socket listener thread function
#   socket_conn, addr = local_master_socket.accept()   
#   ->  this is blocking, this is a persistent "master" socket
#       it listens for new connections and generates a new socket "socket_conn" and links the connection request to that new socket,
#       then continuse listening on the master socket for new connections (while process_running is True)
#       this means multiple clients can connect to the manage_camera.py process over the network and each have their own thread (race conditions?)
#       although this is not possible remotly because of NAT, it would work for a LAN, so multiple computers in the same house can connect to this PC
#       this could be tested with a few virtual machines?
def local_master_socket_listener():
    global process_running, local_host, local_port, local_master_socket
    
    local_master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)     # network stack ("AF_INET"), TCP for transport ("SOCK_STREAM")
    local_master_socket.bind((local_host, local_port))                          # bind to the socket
    local_master_socket.listen(1)                                               # listen to the socket, single connection; can be expanded
    
    while process_running:                                                      # listen for new connections, creating new sockets for each      
        print("[M.C.:] Waiting for a new client to connect to the local master socket...")
        try:
            local_socket, addr = local_master_socket.accept()
        except Exception as e:
            print(f"Problem accepting connection: {e}")
            break
        print("[M.C.:] New client connected: ", local_socket, addr)
        time.sleep(1)
        
        threading.Thread(target=listen_commands_on_socket_thread, name=f"Thread-ClientIP-{addr[0]}", args=(local_socket, addr)).start()
    print("[M.C.:] listen_connections finished")

# Create a new thread for each connection, and name it by IP
# Each of these threads will listen to a master socket (eithr local or VPS from now), for commands
# there is multiple socket_conn objects so can't use a global, just pass new one to thread each time with args=conn
# new thread each time to listen for commands on each connection socket obj (socket_conn)
# The VPS has just one "master" socket, as multiple clients connect to the VPS, not the PC process: PC 1 -> VPS 1 -> Many web clients
# The Local sockets can be many
def listen_commands_on_socket_thread(socket_conn, addr):
    global camera_in_use, exit_command, process_running, recording
    global show_stream, server_viewing

    stop_send_frames_to_VPS_event_obj = threading.Event()
    
    while process_running:
        try:
            print("[M.C.:] Waiting here for a command...")
            data = socket_conn.recv(65536) # <- blocking, waits continuously for new commands
            #65536 bytes overkill ?
            if not data:
                print("[M.C.:] Empty payload == connection closed by client")
                break
            cmd = data.decode().strip()
            print("[M.C.:] Command received:", cmd)
            if cmd == "show_stream":
                # Toggle show_stream and turn on the camera loop
                show_stream = True
                camera_in_use = True
            elif cmd == "hide_stream":
                show_stream = False
            elif cmd == "start_record":
                recording = True
                camera_in_use = True
            elif cmd == "stop_record":
                recording = False
            elif cmd == "start_server_view":
                # new sub-thread each time VPS requests frames over the VPS-master-socket obj ("socket_conn"), pass the thread the socket with args=socket_conn
                # send frames directly back over this TCP connection, TCP is duplex, no need to create a new socket
                if stop_send_frames_to_VPS_event_obj.is_set():
                    stop_send_frames_to_VPS_event_obj.clear()
                VPS_send_thread = threading.Thread(target=send_frames_to_VPS, name=f"VPS_Send_Thread", args=(socket_conn,stop_send_frames_to_VPS_event_obj,))
                VPS_send_thread.start()
                server_viewing = True
            elif cmd == "stop_server_view":
                # signal stop to send_frames_to_VPS(),
                # and toggle stop sending fames to the queue
                stop_send_frames_to_VPS_event_obj.set()
                server_viewing = False
            elif cmd == "exit":
                # Exit is only triggered with local sockets (can be many local sockets) so shut it down, gracefully,
                # and break out of the while loop so as not to wait for another command
                graceful_socket_shutdown(socket_conn)  
                exit_command = True
                return
            cmd = "blank"
        except ConnectionResetError:
            print("[M.C.:] Connection was closed/reset by client.")
            break
        except Exception as e:
            print(f"[M.C.:] Error reading from socket: {e}")
            break
    print("[M.C.:] listen_commands_on_socket_thread finished")

# Send frames to the VPS
def send_frames_to_VPS(socket_conn, stop_send_frames_to_VPS_event_obj):
    while not stop_send_frames_to_VPS_event_obj.is_set():
        try:
            frame = frame_queue.get(timeout=1)
            success, encoded_frame = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50]) # encode it now, before transmitting!!
            if not success:
                raise RuntimeError("Failed to encode frame")
            
            frame_bytes = encoded_frame.tobytes()
            frame_size_desc = struct.pack(">I", len(frame_bytes))  
            socket_conn.sendall(frame_size_desc + frame_bytes)
            print("[M.C.:] Sent 1 frame to the VPS")
        except queue.Empty:
            print("[M.C.:] No frame in queue, continue to next iteration")
            continue # No frame in queue, continue to next iteration
        except Exception as e:
            print(f"Error sending frame: {e}")
            break  # Exit thread on error.  Important to prevent it from trying to send if the connection is broken.

# Main loop for reading 1 frame from the camera and doing processes with it 
# A new webcam_obj is generated upon each restart of this (ie. when camera_in_use is toggled)
# cam_frame_loop() will block until camera_in_use is False or exit_command is True
# if camera_in_use is True but exit_command is also True, cam_frame_loop() will set: 
# camera_in_use = False and process_running = False, killing the entire __main__ loop below
def cam_frame_loop():
    global writer, camera_in_use, exit_command, process_running, webcam_obj, recording
    global local_host, local_port, show_stream, output_dir, clip_interval_secs
    global frame_queue

    print("[M.C.:] Opening webcam.")
    webcam_obj = cv2.VideoCapture(0) 
    if not webcam_obj.isOpened():
        print("[M.C.:] Could not open webcam.")
        return
    else:
        print("[M.C.:] Opened webcam.")
    
    while camera_in_use:
        if exit_command:
            # toggle controls to force _main_ while loop exit
            print("[M.C.:] Exiting...")
            clean_camera()
            camera_in_use = False
            process_running = False
            return

        # read one frame each loop always, if ret is false = no frame available
        ret, frame = webcam_obj.read()  
        if not ret:
            print("[M.C.:] could not read a frame from camera on this iteration")
            pass

        if show_stream:
            cv2.imshow("Live", frame)
            if cv2.waitKey(1) == 27:
                print("[M.C.:] ESC PRESSED!!")
                show_stream = False
                cv2.destroyWindow("Live")
        
        # Obviously not going to try to process and send the frames here, send them to a queue, then use a thread to work off the queue
        if server_viewing: 
            print("sent a frame to the queue")
            try:
                frame_queue.put(frame, block=False)     # put frame in queue
            except queue.Full:
                print("Frame queue is full (or blocked?) - A frame was dropped")
                pass

        if recording:
            if writer is None:
                # = new recording triggered - so create a new filename and 10-second segment
                output_file = os.path.join(output_dir, f"webcam_{time.strftime("%Y%m%d_%H%M%S")}.mp4")
                fourcc = cv2.VideoWriter_fourcc(*'avc1')
                writer = cv2.VideoWriter(output_file, fourcc, 20.0, (640, 480))
                end_time = time.time() + clip_interval_secs
            
            # write a frame each pass until clip time specified has elapsed
            # once elapsed, release the writer so the if statement above registers a new clip filename etc.
            if end_time > time.time():
                writer.write(frame)
            else:
                writer.release()
                writer = None
        
        # recording stopped - release and dereference writer (frees memory)
        if not recording:
            if writer is not None:
                writer.release()
                writer = None
            
            # not recording + not showing screen == camera not in use, so clean_camera() to save resources
            if not show_stream:
                clean_camera()
                camera_in_use = False
                break
        
        time.sleep(FPS)
    print("[M.C.:] cam_frame_loop finished")

def clean_camera():
    print("[M.C.:] Cleaning camera")
    global webcam_obj
    
    # Try to release camera
    if webcam_obj:              
        webcam_obj.release()
    if webcam_obj.isOpened():
        print("[M.C.:] webcam_obj still appears open after release!")
    
    # Close all windows if any exist
    cv2.destroyAllWindows()
    print("[M.C.:] clean_camera finished")

# Gracefully try shut down socket in both directions with .shutdown(socket.SHUT_RDWR)
# And then force close it regardless
def graceful_socket_shutdown(socket_conn):
    print("[M.C.:] Attempting to safely disconnecting the socket", socket_conn)
    # try:
    #     socket_conn.shutdown(socket.SHUT_RDWR)  
    #     print("[M.C.:] Socket shutdown successfully")
    # except OSError as e:
    #     print(f"[M.C.:] Failed to shutdown socket: {e}")
    # except Exception as e:
    #     print(f"[M.C.:] Failed to shutdown socket!: {e}")
    
    # Now force close the socket, regardless if .shutdown() worked or not
    try:
        socket_conn.close()
        print("[M.C.:] Socket closed successfully")
    except OSError as e:
        print(f"[M.C.:] Failed to close socket: {e}")

# cam_frame_loop() will block until camera_in_use is False or exit_command is True
# if camera_in_use is True but exit_command is also True, cam_frame_loop() will set: 
# camera_in_use = False and process_running = False, killing the entire __main__ loop
# But if both are False, the __main__ loop here will keep runing, with a time.sleep(2), awaiting camera_in_use or exit_command to be toggled to True
if __name__ == "__main__":

    # Local socket thread:
    threading.Thread(target=local_master_socket_listener, daemon=True).start()
    # VPS socket thread:
    threading.Thread(target=VPS_master_socket_reverse_listener, daemon=True).start()
    
    while process_running:
        if camera_in_use:
            cam_frame_loop()
        if exit_command:
            break
        time.sleep(2)   # reduces CPU usage while camera not in use

    print("[M.C.:] manage_camera.py exiting...")
