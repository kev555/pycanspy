import socket
import cv2
import pickle
import struct
from flask import Flask, Response, render_template
import threading
import time
import datetime

app = Flask(__name__)
global frame_to_display
frame_to_display = None
lock = threading.Lock()


# socket stuff
host = '127.0.0.1'  # or 'localhost'
port = 5000         # any free port
client_socket = None

def receive_video(server_ip, server_port):
    # """Receives video frames from the client and updates frame_to_display."""
    global frame_to_display, client_socket
    
    # create a socket object (does not connect to anything or open a connection yet)
    if client_socket is None:                                               # socket doesnt exist yet
        print("creating socket...")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)   # try to create it

    try:
        client_socket.connect((host, port)) # ConnectionRefusedError if not working
        print("Connected to socket")
        client_socket.sendall(("start_server_view" + '\n').encode())
    except Exception as e:
        print("no connect to socket")

    data = b""
    payload_size = struct.calcsize("!I")   

    try:
        while True:

            print("remote view] -- loop ran")
            while len(data) < payload_size:
                data += client_socket.recv(4096)  # Increased buffer size
            

            print("data loaded: ", len(data))

            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("!I", packed_msg_size)[0]  

            while len(data) < msg_size:
                data += client_socket.recv(4096)  # Increased buffer size
            
            frame_data = data[:msg_size]
            data = data[msg_size:]

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
                try:
                    ret, buffer = cv2.imencode('.jpg', frame_to_display)
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                    else:
                         yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' +  b'\r\n')
                except Exception as e:
                    print(f"Error encoding frame: {e}")
                    yield (b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n\r\n' +  b'\r\n')
            else:
                yield (b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' +  b'\r\n')
        time.sleep(0.1)

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