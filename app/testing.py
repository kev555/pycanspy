import sys

import cv2


import time

start_time = time.time()

if writer is None:  # means new recording triggered - so create a new filename and 10-second segment
    os.makedirs(output_dir, exist_ok=True)          
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True) 
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True) 
    os.makedirs(output_dir, exist_ok=True)
    start_time = time.time()
    end_time = start_time + clip_interval_secs # unix time is in seconds so just add
    fourcc = cv2.VideoWriter_fourcc(*'H264')  # fourcc = "4 character codec", * = unpack operator, chose H264 (best for web), returns 32bit int codec ID
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"webcam_{timestamp}.mp4") # ".mp4 = use mp4 container"  (best for web)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
            

# print("sfdsdfsdf", cv2.getBuildInformation())


fourcc = cv2.VideoWriter_fourcc(*'XVID')
print(fourcc)


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


