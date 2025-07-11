import socket
import cv2
import pickle
import struct
import os
from flask import Flask, Response, render_template, request, jsonify, send_from_directory
import threading
import time
import datetime
import numpy as np

app = Flask(__name__)
frame_to_display = None
lock = threading.Lock()

FPS = 1 / 5

# socket stuff
client_socket = None
server_recieve_port = 5001
# # server_host = '127.0.0.1'
# # no, stop binding to an internal loopback address, it's only accessible internally, so no use for publicly connecting in, use:
server_host = '0.0.0.0'
# 0.0.0.0 = bind to all IP's on the device, which will include the one assigned to the network interface, 
# I could bind JUST to the network interfaces's IP (146.190.96.130), both would work 
# 0.0.0.0 works fine, but the downside being that 5001 can't be use for binding by any other process
# However servers, and basically every internet connected device, have one primary network interface handling external traffic at a time.
# And usually ther's just one public IP assigned to this default interface (althongh many is possible)
# So under normal circumstances you couldn't bind to 5001 for external listening by multiple processes anyway, 
# as there is only really 1 viable option for that port -> i.e. 146.190.96.130:5001
# so if tl;dr this the verbose recap.... 0.0.0.0 is fine for enabling public out/in access, quickly, easily, persistently

is_client_connected = None
last_connected_state = None
start_server_viewing = None

def create_master_socket():
    global show_stream, recording, writer, camera_in_use, process_running, exit_command
    global server_host, server_recieve_port, server_socket, is_client_connected
    
    # Socket initialization - this is the permenant gateway socket for all connections
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # = "make a socket object which will use the network stack (AF_INET), specifically TCP for transserver_recieve_port (SOCK_STREAM), not UDP"
    
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # force socket re-use probably not safe! - close socket proprtly later - re-use safe shutdown from GUI
    
    server_socket.bind((server_host, server_recieve_port))    # bind to the socket
    server_socket.listen(1)             # listen to the socket, single connection; can be expanded
    
    while True:        # listen for new connections, creating new sockets for each      
        print("Server socket created, waiting here for a new client to connect...")
        try:
            conn, addr = server_socket.accept()     # <- blocking, listen for new connection attempted on this master socket, 
                                                    # then generate a new socket "conn" and link the connection request to that instead,
                                                    # then continue listeing on the master socket here, rinse and repeat
        except Exception as e:
            print(f"Problem accepting connection: {e}")
            break
        
        print("PC app connected!!:") #, conn, addr)
        is_client_connected = True

        threading.Thread(target=send_command_recieve_video, name=f"Thread-ClientIP-{addr[0]}", args=(conn, addr)).start()
        # Create a new thread for each connection, and name it by IP
        # there is multiple conn objects so can't use a global, just pass new one to thread each time with args=conn



def send_command_recieve_video(conn, addr):
    global frame_to_display, start_server_viewing, is_client_connected

    while True:
        print("Should I send a command to the PC app?")
        
        if start_server_viewing is True:
            print("start_server_viewing has been changed to True, so ask PC to start sending")
            max_send_retries = 3 # Try 3 times to send command through socket conn:
            for attempt in range(max_send_retries):
                try:
                    conn.sendall(("start_server_view" + '\n').encode()) # no worry about blocking, this is already in a thread
                    
                    # if this is reached, the message was sent successfully, break out of the for loop without trying the remaining times
                    print("start_server_view message sent to PC")
                    break
                except Exception as e:
                    print(f"Send attempt {attempt+1} failed: {e}")
                    time.sleep(1)
            else:
                raise Exception("Failed to send command after {max_send_retries} attempts.")
            
            # if this is reached, the start_server_view command has been sent, so the manage_camera process should have now started to send frames back through the socket
            pc_is_sending = True

            # now start collecting them frames from the OS buffer
            data_buffer = b""
            fourbyte_un_bigE_struct = struct.calcsize(">I") # an ">I" struct, > = big-endian (TCP/IP standard), I = unsigned int (4 bytes))
            try:
                while start_server_viewing is True:

                    while len(data_buffer) < fourbyte_un_bigE_struct: # read at least 4 bytes before continuing, as the frame lenght size description header is at least needed
                        data_buffer += conn.recv(4096) # blocks until at least 4096 bytes appears in the OS buffer for this socket, reads it then stops blocking
                        if not data_buffer:  # connection closed by client
                                    print("Connection closed by client")
                    
                    frame_size_description = data_buffer[:fourbyte_un_bigE_struct]
                    # grab the first 4 bytes, which notate the size of the frame data, the rest of the bytes are the frame data itself
                    toal_frame_size_as_int = struct.unpack("!I", frame_size_description)[0]     # decode them into an integer value
                    data_buffer = data_buffer[fourbyte_un_bigE_struct:]                         # take the rest of the recieved bytes, - thus trimming the first 4
                    
                    while len(data_buffer) < toal_frame_size_as_int:
                        data_buffer += conn.recv(4096)      # keep reading 4096 bytes from the socket until at least the current frame's worth of data is collected
                        if not data_buffer:                 # connection closed by client
                                    print("Connection closed by client")
                    # If multiple frames are being sent, the final recv() in this loop may contain the start of the next frame.
                    # So extract only this frame's data from the buffer, leaving any trailing data (belonging to the next frame) for the next iteration.
                    frame_data = data_buffer[:toal_frame_size_as_int]
                    # frame_data is now a single full indivdual frame

                    # set the data_buffer to just contain the trailing data, if any, and repeat the reading process on next loop
                    # Note: there could be an edge case where the final frame doesn't display properly if the connection is closed mid-transfer
                    data_buffer = data_buffer[toal_frame_size_as_int:]

                    try:
                        # No pickle, just pass the frame as bytes deirectly to the multipart: (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_to_display + b'\r\n') 
                        with lock:
                            frame_to_display = frame_data
                    except e:
                        print(f"Error reading frame: {e}")
                        continue
            except Exception as e:
                print(f"Error receiving data: {e}")
            time.sleep(1)
        elif start_server_viewing is False:
            if pc_is_sending is True:
                print("start_server_viewing has been changed to False, but pc_is_sending is True, so ask PC to stop sending")
                max_send_retries = 3                        # Try 3 times to send command through socket conn:
                for attempt in range(max_send_retries):
                    try:
                        conn.sendall(("stop_server_view" + '\n').encode()) # no worry about blocking, this is already in a thread
                        
                        # if this is reached, the message was sent successfully, break out of the for loop without trying the remaining times
                        print("stop_server_view message sent to PC")
                        break
                    except Exception as e:
                        print(f"Send attempt {attempt+1} failed: {e}")
                        time.sleep(1)
                else:
                    raise Exception("Failed to send command after {max_send_retries} attempts.")

                pc_is_sending = False   # sent this back to False now
            time.sleep(1)
        else:
            time.sleep(1)

# So when start_server_viewing becomes False, it will break out of the reading loop, but stay in the checking loop,
# and when it become True again it will try to sned the PC start_server_view request again
# No need to conn.close() the socket, just instruct the PC app to stop sending


def make_placholder_frame():
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)  
    # Create black frame, Each frame is uniform and easy to notate structure:
    # ((480, 640, 3)) -> "height 480, width 640, with 3 color channels (RGB)"
    # dtype (uint8)   -> "raw bytes as a flat array of unsigned 8-bit integers."
    
    cv2.putText(
        black_frame,
        "No video stream yet",
        org=(50, 240),               # x, y position of text
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=1,
        color=(255, 255, 255),       # White text
        thickness=2,
        lineType=cv2.LINE_AA
    )
    _, black_frame_encoded = cv2.imencode('.jpg', black_frame)
    return black_frame_encoded



def generate_frames():
    # needs a placeholder, if just an empty frame a page refresh was necessary after client starts streaming... why?
    # "Browsers expect MJPEG streams to begin with a valid JPEG frame. If starting blank or malformed it will lock up.
    
    black_frame_encoded = make_placholder_frame()
    print(black_frame_encoded)


    yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + black_frame_encoded.tobytes() + b'\r\n')

    global frame_to_display
    while True:
        # print("generate_framesssssssssssssssss") 
        # 
        # 
        # THIS DOESNT NEED TO RUN AT ALL IF THE PC IS NOT SENDING ie pc_is_sending = True !!!!!!!!!!!!!!!!!
        time.sleep(FPS)
        with lock:
            if frame_to_display is not None:
                try:
                    yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_to_display + b'\r\n')  # no need for .tobytes() anymore
                except Exception as e:
                    print(f"Error encoding frame: {e}")
                    yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +  b'\r\n') # empty frame (white)
            else:
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + black_frame_encoded.tobytes() + b'\r\n')
                time.sleep(2) # can wait an extra 2 seconds here as the blank image doesnt need to be full FPS


@app.route('/control', methods=['POST'])
def control():
    global start_server_viewing, is_client_connected
    data = request.get_json()
    command = data.get('command')
    print(f"Received command: {command}") # ???????????
    if command in ("Start"):
        start_server_viewing = True
        return f"Command {command} received", 200
    if command in ("Stop"):
        start_server_viewing = False
        # is_client_connected = False # NO THIS SHOULD ONLY CHNAGE WHEN THE SOCKET IS CLOSED FROM THE PC SIDE!!!! OR WHEN THE SOCKET closes abruptly, how do i check for this????
        return f"Command {command} received", 200
    else:
        return 'Invalid command', 400
# api endpoint for recieving a command from webpage
# these Flask routes are same like JS listeners. They are "URL-based event listeners", they dont block obviously, their "listening" is asynchronous
# but the code inside their route function is synchronous as it's running in the current app.run() thread/process, so keep it light
# or use app.run(threaded=True), then every request gets it's own thread
# app.run(host='0.0.0.0', port=1705) == Flask listens on all network interfaces on port 1705.
# So any HTTP request sent to eg.:
# http://localhost:1705/control or http://<your-server-ip>:1705/control ,
# or any IP assigned to your machine on port 1705 will trigger this handler:


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
# Endpoint for publishing the the video feed 
# see SSH tunneling, UDP streaming protocols.txt for details

@app.route('/client_status')
def client_status():
    global last_connected_state

    print(1119999, last_connected_state, is_client_connected)
    print("state 0: ", is_client_connected, last_connected_state)
    
    # Using the global state variable I will just store and refrence the last state vs current state every few seconds..
    while True:
        if is_client_connected != last_connected_state: 
            # passes only if they are not the same, as both variable start off as None this will run only after client has connected
            # last_connected_state is then set to is_client_connected, so on subsequent passes it will not run until something changes
            # so anytine this runs - something has changed, so simply check the current state and set last_connected_state to that value
            # update the html to notate the new state before relooping and waiting for another change to is_client_connected
            print("Connected state changed: ", is_client_connected, last_connected_state)
            if is_client_connected is False: 
                last_connected_state = False
                #print("states 2: ", is_client_connected, last_connected_state)
                return jsonify({"connected": False})
            elif is_client_connected is True:
                last_connected_state = True
                #print("states 3: ", is_client_connected, last_connected_state)
                return jsonify({"connected": True})
            else:
                print("states wtffffffff: ", is_client_connected, last_connected_state)
        # else:
        #     pass
        #     # print("nooo change")
        #     #pass # just keep the connection open if nothing changed == "long polling"
        time.sleep(3)

# /client_status now implements long-polling here to stop constant checks from browser -> server to get the PC app's connected-to-server state
# instead of many repettive GETs now just one "pending" GET
# once a state change is detected (PC app connected or disconnected to the server), update the browser accordingly by responding to the pending GET with return
# after the PC app connects and thus the pending request is responded to, another GET for the status is made immidiatly and this also stays pending until another change
# so just 1 full request-response cycle per status change
# however this now requires doing the constant connected state check directly here in server code (hence the while True loop)
# (would Server Sent Events be better here since this is a specific separate connection?)


# Chrome DevTools trying to check if the site has a known devtools-specific configuration (for debugging, like source maps or remote debugging endpoints).
# actually... something else was delaying the load up not this, not necessary to block
# @app.route('/.well-known/appspecific/com.chrome.devtools.json')
# def suppress_chrome_probe():
#     return '', 204

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/')
def index():
    return render_template('index.html') 
    # the raw video can be viewed directly at: my_server.com/video_feed, is it necessary to not allow this? probably ok

if __name__ == "__main__":
    receive_thread = threading.Thread(target=create_master_socket,)
    receive_thread.daemon = True
    receive_thread.start()
    # run the frame receiving thread as a daemon, letting the OS clean up the sockets if a crash happens
    # acceptable solution for now, prototyping / non-critical system.
    # Later, if need robustness (e.g. production use) can add signal handling, full exception handling / logging, recovery mechanisms.

    # Start flask server:
    app.run(host='0.0.0.0', port=1705, debug=False)     # display port will be 1705

