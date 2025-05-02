import cv2
import threading
import socket
# import time

# global controls
process_running = True
show_stream = False
recording = False
camera_in_use = False
exit_button_pressed = False

# I'm just going to use these global controls and not try to be too clever
# but these could be passed instead of being global...
writer = None
cap = None

# socket stuff
host = '127.0.0.1'  # or 'localhost'
port = 5000         # any free port

conn = None
server_socket = None

def handle_commands():
    # asynchronous, runs in it's own thread. could use signal.pthread_kill to terminate but better to use "shared flag" method - process_running boolean here, 
    # kiling a thread directly can apparently cause a lot of issues on windows espically

    global show_stream, recording, writer, camera_in_use, process_running, exit_button_pressed
    global host, port, conn, server_socket
    # global is not declaring a variable it's saying "Inside this function, when I refer to some_variable, I mean the one from the global scope — not a new local one."
    # without "global", the objects would be re-created inside this scope (Python would re-delare it in here)
    # there is also "nonlocal" to modify variables from an enclosing (but non-global) scope, similar
    # Python allows scope climbing for access, but requires explicit delarations for scope climbing for assignments / modifications.
    # JavaScript's allows scope climbing for assignment and access without explicit declaration, which can cause scope pollution
    
    while process_running:
        # Socket initialization

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        # = "make a socket object which will use the network stack (AF_INET), specifically TCP for transport (SOCK_STREAM), not UDP"
        
        server_socket.bind((host, port)) # bind to the socket
        server_socket.listen(1)  # listen to the socket, single connection; can be expanded

        print("server_socket.getsocknam:::", server_socket.getsockname())

        try:
            print("[SP:] Waiting for GUI to connect to socket...")

            conn, addr = server_socket.accept() # So for handling multiple clients just break them off into a new threads each time here, using some loop logic

            # "accept() -> (socket object, address info)" # "plain-language description" of what the method socket.accept() returns, not very useful info...
            # "(method) def accept() -> tuple[socket, _RetAddress]" # more useful description
            print("conn", type(conn), conn.getsockname()) # <class 'socket.socket'>
            print("addr", type(addr), addr)  # <class 'tuple'>)  ("IP_address" as a string + port as an int))
            
            # https://docs.python.org/3/library/socket.html#socket.socket.accept
            # conn is a new socket object usable to send and receive data on the connection, 
            # address is the address bound to the socket on the other end of the connection

            # So this means .accept() has already done the TCP handshake and has gathered the IP address and
            # temporary port (epherial temporary port) that the client will use for the TCP connection on it's side
            # and stores this all in a newly created socket - "conn". It creates a new socket object why?:
            # to allow one "server_socket" socket object as a master, then as additional clients attempt to establish a connection
            # just spawn new socket objects with that connection already set up. 
            # 
            # While these TCP connections are still alive the conn object can keep communicating with the client.
            # These object dont need to like go through the original server or anything or even use a different port, how?
            # any packets coming from that client address + client epherial port,
            #  the OS will be able to use this to route the packets directly to the correct object based on what object has that _RetAddress
            # client_socket.getpeername() will show the conn objects's (client_ip, client_port)
            # - this process will know excatly what conn object that packet was meant for
            # 
            # HOW excatly do the packets get from the OS to a specific object in a process:
            # The OS maintains a mapping between each socket file descriptor(an integer) and the corresponding kernel-level socket object. 
            # When network data arrives for a specific connection, 
            # the OS uses the connection’s identifying information(the four-tuple of source IP, source port, destination IP, and destination port) 
            # to locate the appropriate socket. It then queues the data in the socket’s kernel buffer. 
            # Your Python process, which holds a reference to the file descriptor(e.g. via the conn object), 
            # can access this data by invoking syscalls like recv(), which read from the kernel buffer via that file descriptor.

            #print("[SP:] GUI connected to socket.")
        except Exception as e:
            #print(f"Problem accepting connection: {e}")
            break

        while process_running:
            # Main process
            try:
                #print("[SP:] Waiting here for a command...")
                data = conn.recv(65536)  # <- blocking, recv = "receive", app will just hang here until a command or exit is recieved
                print("Raw bytes: ", data)
                if not data:                
                    #print("[SP:] No data, connection closed by client)
                    break
                #print(f"[SP:] Command received: {data}") # ?
                cmd = data.decode().strip()
                print("UTF-8 decoded bytes:", cmd)

                # NOTES:
                # With a TCP socket, a client signals termination by sending a TCP packet with a FIN flag (single bit, 1 or 0) and an empty payload
                # The C library and thus Python reads the payload in Bytes and passes it to the application when recv() is called
                # So "data" will be a  python bytes object (you'll see: b'' if printed)
                # If the message was "Hello" you'd see b'Hello', Python's print() auto deocdes ASCII range characters (0-127)
                # If the message was € you'd see b'\xe2\x82\xac' (bytes as Hex) until cmd = data.decode() is called 
                # (.decode() default is UTF-8, which is what most clients will be sending anyway!), 
                # see note Bytes_UFT_encoding_etc.txt for deeper info on bytes and UTF encoding


                # control logic:  !! make this separate function
                if cmd == "show_stream":
                    show_stream = True
                    camera_in_use = True        # Turn the camera loop on after setting things up here
                elif cmd == "hide_stream":
                    show_stream = False
                elif cmd == "start_record":
                    if writer is None:
                        fourcc = cv2.VideoWriter_fourcc(*'XVID')
                        writer = cv2.VideoWriter("output.avi", fourcc, 20.0, (640, 480))
                    recording=True
                    camera_in_use = True        # Turn the camera loop on after setting things up here
                elif cmd == "stop_record":
                    if writer:
                        writer.release()
                        writer=None
                    recording=False
                elif cmd == "exit":
                    #print("[SP:] Exiting...")
                    exit_button_pressed = True  # i think more graceful to exit from the inside camera_control_and_loop, instead of just killing it from here
                    return                      # jump out so as not to wait for another command
                cmd = "noting new"
            except ConnectionResetError:
                #print("[SP:] Connection was closed/reset by client.")
                break
            except Exception as e:
                #print(f"[SP:] Error reading from socket: {e}")
                break
        print ("SUB process finished")

def camera_control_and_loop():
    # Runs once each time camera_in_use is triggered
    global writer, camera_in_use, exit_button_pressed, process_running, cap
    global host, port, conn, server_socket

    
    print("[SP:] Opening webcam.")
    # adding cv2.CAP_DSHOW here make the camera open 5x faster ... 
    # i dont know why this worked found here: https://answers.opencv.org/question/215586/why-does-videocapture1-take-so-long/
    
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
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
            #print("[SP:] could not read frame from camera")
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
    global host, port, conn, server_socket

    #print("[SP:] Cleaning up")
    global writer, cap
    
    # Try to release camera
    if cap:
        #print("[SP:] cap exists, releasing")
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
    
    threading.Thread(target=handle_commands, daemon=True).start() # <- Non-Blocking, thread to listen on socket and relay commands
    
    while process_running:
        if camera_in_use:
            camera_control_and_loop()    # <- Blocking, camera must be turned off first or process_running loop can't end
        if exit_button_pressed:          # <- If exit pressed, process_running will also end, so kill the socket here just befre ending
            print("[SP:] Attempting to safely disconnecting the socket", conn)
            try:
                conn.shutdown(socket.SHUT_RDWR)  # Gracefully shut down both directions
                print("[SP:] Socket shutdown successfully")
            except OSError as e:
                print(f"[SP:] Failed to shutdown socket: {e}")
            except Exception as e:
                print(f"[SP:] Failed to shutdown socketttttttttt: {e}")

            # Now close the socket
            try:
                conn.close()
                print("[SP:] Socket closed successfully")
            except OSError as e:
                print(f"[SP:] Failed to close socket: {e}")
            break
        # is there any way process_running is true while camera in use and exit_button_pressed are false? this would get stuck if so ?????
    print("[SP:] subprocess ended, exiting.")