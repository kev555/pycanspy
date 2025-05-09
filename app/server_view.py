import socket
import cv2
import pickle
import struct
from flask import Flask, Response, render_template
import threading
import time
import datetime
import numpy

app = Flask(__name__)
global frame_to_display
frame_to_display = None
lock = threading.Lock()


# socket stuff
server_ip = '127.0.0.1'  # or 'localhost'
server_port = 5000         # any free port
client_socket = None

def receive_video(host, port):
    # """Receives video frames from the client and updates frame_to_display."""
    global frame_to_display, client_socket
    
    # create a socket object (does not connect to anything or open a connection yet)
    if client_socket is None:                                               # socket doesnt exist yet
        print("creating socket...")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # try to create it

    try:
        client_socket.connect((host, port)) # ConnectionRefusedError if not working
        print("Connected to socket")
        client_socket.sendall(("start_server_view" + '\n').encode())
    except Exception as e:
        print("no connect to socket")

    data_buffer = b""
    fourbyte_un_bigE_struct = struct.calcsize(">I") # an ">I" struct, > = big-endian (TCP/IP standard), I = unsigned int (4 bytes))

    try:
        while True:
            while len(data_buffer) < fourbyte_un_bigE_struct: # read at least 4 bytes before continuing, as the frame lenght size description header is at least needed
                data_buffer += client_socket.recv(4096)
                #print("got some data")
                # sendall() in manage_camera.py can send an arbitrarily large amount of data (image frame), it doesn't have to be < 4096
                # sendall() blocks until all data is sent, or an error occurs, even if this requires multiple .recv(4096)'s
                # .recv() does not block until all data is recieved, it relies on OS kernel buffers between reads
                # ie. after a .recv() of 4096 bytes here, while processing, pickeling and passing them to generate_frames function, 
                # the manage_camera.py will most likely still be .sendall()ing more frames, but they will be stored in the OS kernel buffers unitl
                # .recv() is called again to read then from that buffer. 
                # If the buffer fills up and stays full long enough, the server (manage_camera.py), might raise a BrokenPipeError or ConnectionResetError.

                # TCP ensures reliable, in-order delivery of the raw packets (network level)
                # Python's sendall() ensures an entire payload will be sent via TCP (application level here)
                # The following code organizes the payload into usable image frames using .recv() and byte string slicing (code level here)
                
            
            frame_size_description = data_buffer[:fourbyte_un_bigE_struct]        
            # grab the first 4 bytes, which notate the size of the frame data
            # the rest of the bytes are the frame data itself
            toal_frame_size_as_int = struct.unpack("!I", frame_size_description)[0]     # decode them into an integer value
            data_buffer = data_buffer[fourbyte_un_bigE_struct:]                         # take the rest of the recieved bytes, - thus trimming the first 4
            
            while len(data_buffer) < toal_frame_size_as_int:  
                #print("got some more data")  
                data_buffer += client_socket.recv(4096)         # keep reading 4096 bytes from the socket until at least the current frame's worth of data is collected
            # If multiple frames are being sent, the final recv() in this loop may contain the start of the next frame.

            # So extract only this frame's data from the buffer, leaving any trailing data (belonging to the next frame) for the next iteration.
            frame_data = data_buffer[:toal_frame_size_as_int]
            # frame_data is now a single full indivdual frame

            # set the data_buffer to just contain the trailing data, if any, and repeat the process 
            # Note: there could be an edge case where the final frame doesn't display properly if the connection is closed mid-transfer
            data_buffer = data_buffer[toal_frame_size_as_int:]

            try:
                frame = pickle.loads(frame_data)
                with lock:
                    frame_to_display = frame
            except pickle.UnpicklingError as e:
                print(f"Error unpickling frame: {e}")
                continue

    except Exception as e:
        print(f"Error receiving data: {e}")
    finally:
        client_socket.close()
        print("Socket closed")

def generate_frames():
    """Yields the current video frame for display in the browser."""
    global frame_to_display
    while True:
        with lock:
            if frame_to_display is not None:
                try: # ret, buffer = cv2.imencode('.jpg', frame_to_display) ### NOT GOING TO NEED TO ENCODE ON THIS SIDE
                    yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_to_display.tobytes() + b'\r\n') # can just do frame_to_display.toBtes here directly
                except Exception as e:
                    print(f"Error encoding frame: {e}")
                    yield (b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n\r\n' +  b'\r\n')
            else:
                try:
                    static_frame_bytes = numpy.random.randint(0, 255, (480, 640, 3), dtype=numpy.uint8) # use a numpy arry to make a fake static fame like old TVs
                    ret, static_frame = cv2.imencode('.jpg', static_frame_bytes)
                    if ret:
                        yield (b'--frame\r\n'
                                    b'Content-Type: image/jpeg\r\n\r\n' + static_frame.tobytes() + b'\r\n') # can just do frame_to_display.toBtes here directly
                except Exception as e:
                    print(f"Error encoding frame: {e}")
                    yield (b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n\r\n' +  b'\r\n')
        time.sleep(1 / 30)  # 30 FPS

@app.route('/video_feed')
def video_feed():
    """Flask route to serve the video stream."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
@app.route('/')
def index():
    # Not entirely necessary, can be viewed directly at: my_server.com/video_feed
    return render_template('index.html')

if __name__ == "__main__":

    receive_thread = threading.Thread(target=receive_video, args=(server_ip, server_port)) # Start the frame receiving thread
    receive_thread.daemon = True
    # running the thread as a daemon and letting the OS clean up the sockets if a crash happens is an acceptable solution for now, 
    # especially for prototyping / non-critical system
    # Later, if need robustness (e.g. production use), we can add signal handling, full exception handling / logging, recovery mechanisms.
    receive_thread.start()
    app.run(host='127.0.0.3', port=3333, debug=False)