import socket
import cv2
import struct
import os
from flask import Flask, Response, render_template, request, jsonify, send_from_directory
import threading
import time
import numpy as np
import select
import ssl


app = Flask(__name__)
frame_to_display = None
lock = threading.Lock()
FPS = 1 / 5

# socket stuff
local_master_socket = None
server_recieve_port = 5001
server_host = '0.0.0.0'

is_pc_connected = None
last_connected_state = None
start_server_viewing = None
is_pc_sending_frames = None

connected_state_change_event = threading.Event()

# PC app disconnects -> monitor_disconnect() function select.select's the socket and then MSG_PEEK's it every 1 second 
# -> if in ready state, no problem - do nothing, but when an connection error or clean disconnected state (b'') is seen,
# it changes is_pc_connected = False
# is_pc_connected toggle then triggers @app.route('/client_status') logic,
# the new current state (disconnected) is updated to the Web browser client by responding to the pending GET
# a new pending GET for client status is immidiatly sent, awaiting another is_pc_connected state change (to connected)

# it's a pretty clean flow apart from @app.route('/client_status') logic -> 
# Im using 2 global vars for present and past state and comparing contiuously for change
# instead should be using a threading.Event


# montiors a socket for disconnection
# interestingly if socket.close() is used (in manage_camera) it triggers exception (ConnectionResetError, ConnectionAbortedError),
# whereas if socket.shutdown(socket.SHUT_RDWR) is used, it sends the b'' so "if not data" is properly triggered
def monitor_disconnect(local_TCP_connected_socket):
    global is_pc_connected
    while True:
        try:
            # Wait up to 1 second for readability
            ready, _, _ = select.select([local_TCP_connected_socket], [], [], 1.0)
            if local_TCP_connected_socket in ready:
                data = local_TCP_connected_socket.recv(1, socket.MSG_PEEK)
                if not data:
                    print("Client disconnected!")
                    #is_pc_connected = False
                    set_pc_connection_state(False)
                    break
        except (ConnectionResetError, ConnectionAbortedError):
            print("Client disconnected abruptly")
            #is_pc_connected = False
            set_pc_connection_state(False)
            break
        except Exception as e:
            print(f"Monitor error: {e}")
            break
        time.sleep(0.5)

# Important info on the sockets:
# Both master and accepted sockets are instances of the same class (socket.socket)
# The master socket is in passive mode:
# It waits for clients to connect.
# It uses .bind() and .listen().
# It cannot send or receive data.
# The accepted socket is in active mode:
# Returned by .accept().
# Represents a unique TCP connection.
# Can send and receive data.
# The OS distinguishes multiple connections on the same server port by tracking the full 4-tuple:
# (server_ip, server_port, client_ip, client_port).
# The master (listening) socket is always bound to a 2-tuple: (server_ip, server_port)
# It listens on that IP and port for incoming connections but is not connected to any client yet.
# The full 4-tuple only exists on accepted/connected sockets, where the client IP and client port come into play.

# You should wrap accepted sockets in TLS, never the master socket.
# Wrapping the master socket in TLS is fundamentally wrong because TLS handshake needs an established connection to start.

def create_master_socket():
    global server_host, server_recieve_port, local_master_socket, is_pc_connected

    local_master_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    local_master_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # i think i used this when windows locked a port from a dead process, is this safe??
    local_master_socket.bind((server_host, server_recieve_port))
    local_master_socket.listen(1)

    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile="certs/my_cert.pem", keyfile="certs/my_key.pem")

    while True:  
        print("Server socket created, waiting here for a new client to connect...")
        try:
            local_TCP_connected_socket, addr = local_master_socket.accept()
            try:
                local_TCP_connected_socket = context.wrap_socket(local_TCP_connected_socket, server_side=True)
            except ssl.SSLError as e:
                print(f"[!] SSL error: {e}")
        except Exception as e:
            print(f"Problem accepting connection: {e}")
            break

        print("PC app connected!!:")
        set_pc_connection_state(True)

        # Start the monitor_disconnect and send_command_recieve_video
        threading.Thread(target=monitor_disconnect, args=(local_TCP_connected_socket,), daemon=True).start()
        threading.Thread(target=send_command_recieve_video, name=f"Thread-ClientIP-{addr[0]}", args=(local_TCP_connected_socket, addr)).start()

# This thread / function is created for each new connection to the server from PC, although that's just once for now
# when PC disconnects (is_pc_connected = False !) the while should stop running, but will it destory the socket? of course... that IS disconnecting, 
# so then just make sure everthing is clean after a socket disconnection (listen for it with xxx
# then just make sure it's ready to re-acdept the connection
# So assuming the PC app abruptly disconnects the socket, how can i detect and deal with it here?
# actually the way is to check at every blocking send or recieve operation  revc(), sendall(), send() etc
# as already knonw at this point-> an empty byte string "b''" will be read upon a disconnection, so check for that at the revc(),
# sendall() or send() will also detect it with raising a BrokenPipeError or ConnectionResetError

# SOO: when a connection break is detected -> is_pc_connected should be set to False
# Then add the logic to clean and re-await new connection
# also ive already tried to designed the logic for checking an notifying the user of connected state in the:
# 
# @app.route('/control', methods=['POST'])
# But this was when i thought that "Stop" would actually be breaking the connecton,
# can this logic be re-used or is it wasted!?


## ACTUALLY IM GETTING THIS CONFUSED /CLIENT_STATUS WAS FOR DECTING CONNECTION AND YESSSS OF COUNRS I WILL USE THIS WHEN THE LOGIC IS IMPLEENTED CORRECTLY!!!....

# So when start_server_viewing becomes False, it will break out of the reading loop, but stay in the checking loop,
# and when it become True again it will try to send the PC start_server_view request again
# No need to local_TCP_connected_socket.close() the socket, just instruct the PC app to stop sending

# start_server_viewing = False + is_pc_sending_frames = False ---> re-loop
def send_command_recieve_video(local_TCP_connected_socket, addr):
    global frame_to_display, start_server_viewing, is_pc_connected, is_pc_sending_frames

    # break the if statment in here up into if start_server_viewing is True: and  if start_server_viewing is False and is_pc_sending_frames is True:
    # it too many lines in one if else

    while is_pc_connected: # this could just be True still tbh ..  im killing the thread with a return anyway
        #print("Should I send a command to the PC app?")
        if start_server_viewing is True:
            print("start_server_viewing has been changed to True, so ask PC to start sending")
            max_send_retries = 3
            for attempt in range(max_send_retries):
                try:
                    local_TCP_connected_socket.sendall(("start_server_view" + '\n').encode())
                    # if reached, message sent, break out of for loop
                    print("start_server_view message sent to PC")
                    break
                except (BrokenPipeError, ConnectionResetError) as e:
                        print(f"Connection broken during send attempt {attempt+1}: {e}")
                        # So what to do now? set is_pc_connected to false, then ...? 
                        # break out of the for loop and continue, or return out of the entire while loop?
                        # no i cant contine ... it will start trying to read from a broken socket below.. so need to return out and end this hread.. but how to do it gracefully??

                        # Yes im overthinking this
                        # "Python’s threading.Thread is designed so that when the target function finishes (via return or hitting the end), 
                        # the thread ends — no manual memory cleanup is needed."

                        # what else needs to be done to ensure the thread will start again upon new re-connection?
                        # nothing i think, the master socket listening line:
                        # local_TCP_connected_socket, addr = local_master_socket.accept() will just keep waiting and accepting new connections,
                        # but will local_master_socket.listen(1) affect this? will a broken socket be considered closed??
                        # oh never mind that "backlog size" is only for the master socket itself not the cild sockets ot creates 
                        # the broken local_TCP_connected_socket object will just die and be cleaned with the thread
                        # so really not much to do.... just set is_pc_connected = False return out of the loop and let this thread fucntion die,
                        # but make sure the @app.route('/client_status') logic update the index of connecton status + pending GET restarts 

                        set_pc_connection_state(False)
                        return
                except Exception as e:
                    print(f"Send attempt {attempt+1} failed: {e}")
                    time.sleep(1)
            else:
                raise Exception("Failed to send command after {max_send_retries} attempts.")
            
            # if reached, start_server_view command sent, manage_camera should be sending frames back through the socket now
            is_pc_sending_frames = True
            # now start collecting those frames from the OS buffer
            data_buffer = b""
            fourbyte_un_bigE_struct = struct.calcsize(">I")
            try:
                while start_server_viewing is True:

                    while len(data_buffer) < fourbyte_un_bigE_struct:
                        chunk = local_TCP_connected_socket.recv(4096)
                        if not chunk:
                            raise ConnectionAbortedError("Client disconnected")
                        data_buffer += chunk
                    
                    frame_size_description = data_buffer[:fourbyte_un_bigE_struct]
                    toal_frame_size_as_int = struct.unpack("!I", frame_size_description)[0]
                    data_buffer = data_buffer[fourbyte_un_bigE_struct:]
                    
                    while len(data_buffer) < toal_frame_size_as_int:
                        chunk = local_TCP_connected_socket.recv(4096)
                        if not chunk:
                            raise ConnectionAbortedError("Client disconnected")
                        data_buffer += chunk

                    frame_data = data_buffer[:toal_frame_size_as_int]
                    data_buffer = data_buffer[toal_frame_size_as_int:]

                    try:
                        with lock:
                            frame_to_display = frame_data
                    except e:
                        print(f"Error reading frame: {e}")
                        continue

            except (ConnectionResetError, ConnectionAbortedError) as e:
                    print(f"Client disconnected: {e}")
                    # raise # ... no need to raise to anywhere, just return out and let thread die,
                    # setting is_pc_connected = False should notify the user html via the /client_status GET logic
                    
                    set_pc_connection_state(False)
                    return
            except Exception as e:
                print(f"Error receiving/reading data: {e}")
            time.sleep(1)
        elif start_server_viewing is False:
            if is_pc_sending_frames is True:
                print("start_server_viewing has been changed to False, but is_pc_sending_frames is True, so ask PC to stop sending")
                max_send_retries = 3 
                for attempt in range(max_send_retries):
                    try:
                        local_TCP_connected_socket.sendall(("stop_server_view" + '\n').encode())
                        
                        # if this is reached, the message was sent successfully, break out of the for loop without trying the remaining times
                        print("stop_server_view message sent to PC")
                        break
                    except Exception as e:
                        print(f"Send attempt {attempt+1} failed: {e}")
                        time.sleep(1)
                else:
                    raise Exception("Failed to send command after {max_send_retries} attempts.")

                is_pc_sending_frames = False
            time.sleep(1)
        else:
            # start_server_viewing has not been toggled at all yet, ie. Start or STop has not been pressed at all, do nothing
            time.sleep(1)



def make_placholder_frame(frame_message):
    placholder_frame = np.zeros((480, 640, 3), dtype=np.uint8)  
    # Create black frame, Each frame is uniform and easy to notate structure:
    # ((480, 640, 3)) -> "height 480, width 640, with 3 color channels (RGB)"
    # dtype (uint8)   -> "raw bytes as a flat array of unsigned 8-bit integers."
    
    cv2.putText(
        placholder_frame,
        frame_message,
        org=(50, 240),               # x, y position of text
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=1,
        color=(255, 255, 255),       # White text
        thickness=2,
        lineType=cv2.LINE_AA
    )
    _, placholder_frame = cv2.imencode('.jpg', placholder_frame)
    return placholder_frame


# THIS DOESNT NEED TO RUN AT ALL IF THE PC IS NOT SENDING ie is_pc_sending_frames = True !!!!!!!!!!!!!!!!!
# can i just change the while to: "while is_pc_sending_frames is True:" ??
def generate_frames():
    global frame_to_display, is_pc_sending_frames

    no_stream_yet_placeholder = make_placholder_frame("No video stream yet")
    error_encoding_placeholder = make_placholder_frame("Error encoding frame")
    no_frame_in_queue_placeholder = make_placholder_frame("No frame in queue")

    # needs a placeholder sent at the start, if just an empty frame a page refresh was necessary after client starts streaming... why?
    # "Browsers expect MJPEG streams to begin with a valid JPEG frame. If starting blank or malformed it will lock up.
    
    while True:
        if is_pc_sending_frames is False or is_pc_sending_frames is None:
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + no_stream_yet_placeholder.tobytes() + b'\r\n')
            time.sleep(1) # sleep a little bit if nothng being sent to VPS
        else:
            time.sleep(FPS) 
            # sleep same rate as FPS set for VPS - this could be different from desktop so save bandwidth,
            # so should also include the rate at which the frames are being added to the queue in the PC to be eficent,
            # ie VPS_framerate variable, add to the send queue in manage_camera at that rate, and display here at that rate too,
            # should be changeable failrly eazily from the web app and/or from the GUI??
            with lock:
                if frame_to_display is not None:
                    try:
                        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame_to_display + b'\r\n')  # no need for .tobytes() anymore
                    except Exception as e:
                        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + error_encoding_placeholder.tobytes() + b'\r\n')
                else:
                    yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + no_frame_in_queue_placeholder.tobytes() + b'\r\n')
                    time.sleep(0.2) # sleep a little bit if no frame in queue

@app.route('/control', methods=['POST'])
def control():
    global start_server_viewing, is_pc_connected

    if is_pc_connected:         # Only allow changing streaming state when the PC client is actually connected...!
        data = request.get_json()
        command = data.get('command')
        print(f"Received command: {command}") # ???????????
        if command in ("Start"):
            start_server_viewing = True
            return f"Command {command} received", 200
        if command in ("Stop"):
            start_server_viewing = False
            return f"Command {command} received", 200
        else:
            return 'Invalid command', 400
    else:
        return 'PC not connected', 503
# api endpoint for recieving a command from webpage
# these Flask routes are same like JS listeners. They are "URL-based event listeners", they dont block obviously, their "listening" is asynchronous
# but the code inside their route function is synchronous as it's running in the current app.run() thread/process, so keep it light
# or use app.run(threaded=True), then every request gets it's own thread
# app.run(host='0.0.0.0', port=1705) == Flask listens on all network interfaces on port 1705.
# So any HTTP request sent to eg.:
# http://localhost:1705/control or http://<your-server-ip>:1705/control ,
# or any IP assigned to your machine on port 1705 will trigger this handler:


# Endpoint for publishing the the video feed 
# see SSH tunneling, UDP streaming protocols.txt for details
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


# Function to safely change connection state
def set_pc_connection_state(value):
    global is_pc_connected
    if is_pc_connected != value:            # Just quickly makes sure no inconsistencys 
        is_pc_connected = value             # Set the state to the var
        connected_state_change_event.set()      # Wake up waiting threads
        connected_state_change_event.clear()    # resets the event back to an "unset" state

# event.set() — "Unblock all current waiters"
# Sets the internal flag to True.
# All threads that are currently calling event.wait() will immediately unblock.
# Any future calls to event.wait() will also not block, as long as the flag remains set.
# Think of set() as ringing a bell: "Wake up, the thing you’re waiting for has happened!"

# event.clear() — "Reset the event back to blocking mode"
# Sets the internal flag to False.
# Future calls to event.wait() will block again, until set() is called once more.
# Think of clear() as silencing the bell so the next listener will wait until it's rung again.

@app.route('/client_status_reloadCheck')
def client_status_reloadCheck():
    global is_pc_connected
    return jsonify({'connected': is_pc_connected})  # Respond to web client

# in Flask's each route handler runs in its own thread by default, no worry about blocking
@app.route('/client_status')
def client_status():
    # This should actually be all that's needed here:
    global is_pc_connected
    connected_state_change_event.wait()                 # Wait until state changes before continuing
    return jsonify({'connected': is_pc_connected})  # Respond to web client
    
    # global last_connected_state, is_pc_connected

    # print(1119999, last_connected_state, is_pc_connected)
    # #print("state 0: ", is_pc_connected, last_connected_state)
    
    # # Using the global state variable I will just store and refrence the last state vs current state every few seconds..
    # while True:
    #     if is_pc_connected != last_connected_state: 
    #         # passes only if they are not the same, as both variable start off as None this will run only after client has connected
    #         # last_connected_state is then set to is_pc_connected, so on subsequent passes it will not run until something changes
    #         # so anytine this runs - something has changed, so simply check the current state and set last_connected_state to that value
    #         # update the html to notate the new state before relooping and waiting for another change to is_pc_connected
    #         print("Connected state changed: ", is_pc_connected, last_connected_state)
    #         if is_pc_connected is False: 
    #             last_connected_state = False
    #             print("states 2: ", is_pc_connected, last_connected_state)
    #             return jsonify({"connected": False})
    #         elif is_pc_connected is True:
    #             last_connected_state = True
    #             print("states 3: ", is_pc_connected, last_connected_state)
    #             return jsonify({"connected": True})
    #         else:
    #             print("states wtffffffff: ", is_pc_connected, last_connected_state)
    #     # else:
    #     #     pass
    #     #     # print("nooo change")
    #     #     #pass # just keep the connection open if nothing changed == "long polling"
    #     time.sleep(1)

# /client_status now implements long-polling here to stop constant checks from browser -> server to get the PC app's connected-to-server state
# instead of many repettive GETs now just one "pending" GET
# once a state change is detected (PC app connected or disconnected to the server), update the browser accordingly by responding to the pending GET with return
# after the PC app connects and thus the pending request is responded to, another GET for the status is made immidiatly and this also stays pending until another change
# so just 1 full request-response cycle per status change
# however this now requires doing the constant connected state check directly here in server code (hence the while True loop)
# (would Server Sent Events be better here since this is a specific separate connection?)


# Chrome DevTools trying to check if the site has a known devtools-specific configuration (for debugging, like source maps or remote debugging endpoints).
@app.route('/.well-known/appspecific/com.chrome.devtools.json')
def suppress_chrome_probe():
    return '', 204

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

