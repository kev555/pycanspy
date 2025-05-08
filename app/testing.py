

import os
#os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"
import cv2

cap = cv2.VideoCapture(0, cv2.CAP_MSMF)

camera_fps = cap.get(cv2.CAP_PROP_FPS)
print(camera_fps)


# time_per_frame = 1 / camera_fps
# print(time_per_frame)





##############################
##############################
##############################
##############################


# blah = 1
# def lala():
#     print (blah)
# print(blah)
# lala()


# count = 10  # Global variable
# def my_function():
#     print(count)  # Trying to print 'count' before assignment
#     #count = 5     # Local variable assignment


# my_function()  # This will raise an UnboundLocalError
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
