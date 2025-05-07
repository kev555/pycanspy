

camera_fps = None
time_per_frame = None
frame_queue = queue.Queue(maxsize=300)
# queue.Queue(maxsize=200) = 200 fames max
# if frames are being produced MUCH faster than being consumed the Queue will fill up 
# "except queue.Full" be raised when trying to .put another frame on the queue (in cam_frame_loop)
# although this won't fail it will cause frames to be dropped from the remote viewing
# with 300 frames Queue and ~30 fps camera == 10 delay before starting to drop frames

####



global frame_queue, time_per_frame, camera_fps





def send_frame_remote(conn):
    while remote_viewing:
        try:
            frame = frame_queue.get(timeout=1)            # Get frame from queue, with timeout

####

elif cmd == "remote_view":      
    # additional new sub-thread each time each remote connection socket obj (conn)
    # send over the same (conn) TCP connection, (TCP is duplex), no need to creat a new socket / TCP connection
    # two (or more) threads can safely read from the same queue.Queue in Python
    # there is multiple conn objects so can't use a global conn, just pass new one to thread each time with args=conn
    new_sub_thread = threading.Thread(target=send_frame_remote, name=f"Sub-Thread-ClientIP-{addr[0]}", args=(conn))
    new_sub_thread.start()
    remote_viewing=True

####


def send_frame_remote(conn):
    while remote_viewing:
        try:
            frame = frame_queue.get(timeout=1)            # Get frame from queue, with timeout
            data = pickle.dumps(frame)                      # Serialize the frame into bytes
            message_size = struct.pack("L", len(data))      # Send size in an "L" struct (32 bit unsigned long integer)
            conn.sendall(message_size + data)               # Send the frame
        except queue.Empty:
            continue # No frame in queue, continue to next iteration
        except Exception as e:
            print(f"Error sending frame: {e}")
            break  # Exit thread on error.  Important to prevent it from trying to send if the connection is broken.






####
    if camera_fps is None: 
        camera_fps = webcam_obj.get(cv2.CAP_PROP_FPS)   # get the FPS of this camera, if not gathered already (so at this stage only 1 cam per program instance)
        print("[SP:] gegwtgwrtggrtm.",camera_fps)
        time_per_frame = 1 / 30               # exact time needed for the camera to supply 1 frame

        #####
        if remote_viewing: # Obviously not going to try to process and send the frames here, send them to a queue, then use a thread to work off the queue
            try:
                frame_queue.put(frame, block=False)     # put frame in queue
            except queue.Full:
                print("Frame queue is full or blocked? - A frame was dropped")
                pass                                    # pass = no action needed placeholder
        
        if not remote_viewing:
            # kill the remoe_viewing_thread
            pass
        
        elapsed_time = time.time() - start_time         # gather the time it took to read a frame into this process (+ other operations)
        time.sleep(max(0, time_per_frame - elapsed_time))   # if less than time needed for camera to provide 1 frame as readable - sleep for the remainder
        
    






















import cv2
import time

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

camera_fps = cap.get(cv2.CAP_PROP_FPS)
print(camera_fps)
time_per_frame = 1 / camera_fps
print(time_per_frame)






# blah = 1

# def lala():
#     print (blah)

# print(blah)
# lala()


count = 10  # Global variable


def my_function():
    print(count)  # Trying to print 'count' before assignment
    #count = 5     # Local variable assignment


my_function()  # This will raise an UnboundLocalError

# THIS IS WEIRD:
# But is it using ISO/IEC 8859-1 (LATIN-1) or Windows-1252 (CP-1252) so?
# 0x80 in windows-1252 is "€" in ISO/IEC 8859-1 (Latin-1) 0x80 is blank
# Test for €:
# str_0x80 = "\x80"
# print(str_0x80) # Empty output 

# test2 = "¡"
# print("size:", sys.getsizeof(test2)) # size: 60
# # test2 = "£¢"
# print("size:", sys.getsizeof(test2)) # size: 59

#  HUHhhhhhhhhhh????????

# bytes_as_string = "0x82" 
# print(bytes_as_string) # output: "â¬" # SO WHY THISSSS!!!!!!!!!!
# # print(0x82)
# # print(0b101010)
# # raw_string = r"0b101010"
# # print(raw_string)


