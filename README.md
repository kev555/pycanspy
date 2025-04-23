Re-do of a college project.  
The original project idea was a home surveillance system software suite using just a Windows laptop and some cheap usb webcams connected.  
Providing a cheap alternative to purchasing a real security camera set up. As even IP cameras at the time were not as cheap (2015 vs 2025).  
The original project used C++ OpenCV library for image processing and C++ for the GUI using Qt Creator.
That was quite a steep learning curve for me at the time (dealing with threads).
Perhaps this time time just use a single built in webcam, with the idea being an app to watch your laptop while you are away, such as in cafe's or co working spaces.
At the time I also wrote a small webapp in Angular or React. To display + control the Windows program and view live streams and saved clips remotely. 
However I didn't get the webapp connected to the windows gui application properly at the time.

**Goals for this project:**  
1. Re-write the GUI using something simpler than C++ with QT such as Java Swing or Python tkinter
2. Re-write the motion detection code or import the old
3. Re-write the remote webapp / phone app (cross platform?)
4. Get the remote app(s) fully connected to the desktop app this time

**Development steps:**  
- [x] Open video source (webcam) and save to disk  
- [x] Make sure locking the screen doesn't stop recording, so screen can be locked and still secure 
    - ~~done using a service with the win32service module~~
    - changed to just using a python "subprocess", seems to still record on screen lock, no need for a service  
- [x] Make a simple GUI to start / stop the recording  
- [x] Create a stream for live viewing as well as saving to disk (local live viewing first, remote live viewing next)  
    - This now means no more saving the video from the camera directly, as it's needed for multiple output paths now — disk and screen  
- [ ] Enable the stream to be also viewed remotely in P2P way  
- [ ] Enable the stream to be pushed to a server in case P2P is not possible due to NAT or other restrictions (also allows a set of cloud backups if the user machine fails)  
- [ ] Import the old C++ OpenCV code for motion detection and link it in OR re-write the logic using Python's OpenCV library  
- [ ] Then add the option to only record on motion detection, saving lots of space  
- [ ] Add an alert method that can reach smartphone (email from the PC email client → generic Android alert app)  
- [ ] Add more features to the Python GUI OR make the GUI web app (HTML, CSS, JavaScript) from the beginning so it can be loaded from any device  
    .. Then the Python "GUI" simply functions as a control server, taking messages from either local browser app or remote browser app interchangeably
