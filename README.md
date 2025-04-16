Re-do of a college project.
The original project idea was a home surveillance system software suite using just a Windows laptop with some cheap usb webcams connected.
Providing a cheap alternitive to purchasing a real security camera set up, as even IP cameras + set up at the time were not as cheap as today (2015 vs 2025).
The original project used C++ OpenCV library for image processing and C++ for the GUI using Qt Creator.
That was quite a steep learning curve for me at the time (dealing with threads )

At the time I also wrote a small webapp in Angular or React, I can't remeber which, to display / control the Windows program + View the webcam streams and saved clips remotly.
However I didn't get the  webapp connected to the windows gui application properly at the time.

Goals for this project:
1. Re-write the GUI using something simpler than C++ with QT such as Java Swing or Python tkinter

Developemnt steps:
 - Open video source (webcam) and save to disk - done
 - Make sure locking the screen doesn't stop recording as the PC will need to be left on always so screen will be locked.
    - done using a service with win32service
 - Make a simple GUI to start / stop the recording
 - Stream the recordings to screen for live viewing (and later for remote live viewing)
 - 
