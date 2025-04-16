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
 - Make sure locking the screen doesn't stop recording as the PC will need to be left on always so screen will be locked - done
    -  ~~done using a service with win32service~~ - changed to just using a subprocess, seems to still record on screen lock, no need for a service
 - Make a simple GUI to start / stop the recording - done
 - Stream the recordings for live viewing as well as saving to disk (local live viewing first remote live vewing next)
 - Enable the stream to be viewed remotly, directly... ie. P2P
 - Enable the stream to be pushed to a server in a case where P2P is not possible (also allows a set of cloud back ups if the user machine fails)
 - Import the old C++ OpenCV code for motion detection and link it in or re-write the logic using Python's OpenCV library
 - Then add the option to only record on motion detection, saving lots of space
 - Add an alert method that can reach smartphone (email from the PC email client -> generic android alert app)

 - Add more features to the Python GUI OR make the GUI web app (html, css, javascript) from the beginning so it can be loaded from any device,
    Then the Python "GUI" simply function as a control server, taking messages from either local browser app or remote browser app interchangably
 - 