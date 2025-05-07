## Changelog

### Version 2.0

#### Changes
- **Video format changed to more web-friendly versions:**
  - Make sure to download `openh264-1.8.0-win64.dll` and keep it in the same directory as the app, or OpenCV will automatically switch the codec and only show a warning.

- **Implemented multiple socket connections per camera process:**
  - `handle_commands` is now split into `listen_connections` and `listen_commands`.
  - NEEDS MORE TESTING
  
  **`listen_connections`:**
  - Listens on the same socket object/port continuously (5000).
  - Creates a new connected socket object for each new connection (a new TCP connection with a new port).
  - Spawns a new thread with a fresh instance of `listen_commands` for each connection.
  
  **`listen_commands`:**
  - In a thread, listens on the new socket object/port continuously.
  - Sends commands back to the main process via shared flags.

- **Code cleanup:**
  - Removed excessive inline comments that cluttered the code.
  - Plan: Add concise citation-style "comment markers" at key points in the code, with a separate document (e.g., "Comments Explained") containing extended details.


#### Next Steps
- **Optimize the capture frame loop:**
  - Check the advertised FPS of the camera, measure time taken to read a frame, and do other processes in the loop.
  - Wait for the difference in time at the bottom of the loop before running it again, avoiding capturing an already captured frame and saving processing power and data.
  
- **Remote viewing:**
  - Initially via an external server, as most users will likely run this app behind NAT.
  - Later, implement P2P functionality, with various NAT traversal methods.

### End of Version 2.0 Changes


### Version 2.1

...

###