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


#### Next Steps / TO DO:
- ~~ **Optimize the capture frame loop:**~~
  ~~ - Check the advertised FPS of the camera, measure time taken to read a frame, and do other processes in the loop. ~~
  ~~- Wait for the difference in time at the bottom of the loop before running it again, avoiding capturing an already captured frame and saving processing power and data.~~
  Not nesessary, as it seems .read() will wait on frames from the cam in 99% of cases
  
- **Remote viewing:**
  - Initially via an external server, as most users will likely run this app behind NAT.
  - Later, implement P2P functionality, with various NAT traversal methods.

### End of Version 2.0 Changes

---

### Version 2.0.1

- **Fixed sockets logic in `manage_camera` process:**
  - `listen_connections()` → socket initialization moved outside the loop, as this is the permanent gateway socket for all connections to the `manage_camera.py` process.
  - Each new connection no longer destroys the gateway socket.

- **Added ability to view on a remote server (locally for now):**

  **Method — `manage_camera.py.send_frame_server()`:**
  1. The `listen_commands()` socket thread receives a `"remote_view"` command.
  2. `cam_frame_loop` is set to save every new frame to a global queue.
  3. The same socket is passed to a new sub-thread created for sending data to the server.
  4. This sub-thread asynchronously reads frames from the global queue and sends them *back* through that socket.

     - There might be a delay between the queue and the actual live video due to network transmission.
     - This is why a separate thread + queue are required.
     - If the queue can hold 300 frames (e.g., @30fps), that equals ~10 seconds of potential delay on the remote viewing device.
     - After that, frames would begin to drop until the queue clears.

  **`server_view.py`:**
  - Connects to `manage_camera.py` via the gateway socket.
  - Receives frames as bytes → de-pickles them → displays them at endpoint: `http://127.0.0.3:3333/video_feed`.
  - Flow: `frame` → `pickle` → `queue` → `remote server` → `unpickle` → `display`.

**Notes:**
- `manage_camera.py` acts as the **server**, even for remote viewing.
- The remote server must initiate the connection.
- This will require a **reverse SSH tunnel** from the PC to the remote VPS.
- For now, the `GUI.py` must launch the `manage_camera` process.
- Once the gateway socket is open in `manage_camera`, the remote server (currently running locally) can connect to it (currently via `localhost:5000`).

---

#### Next Steps / TO DO:

**Minor:**
- More testing of multiple functionalities running simultaneously.
- Add a reverse SSH tunnel to a remote public server.
- Get `server_view.py` running on the server and accessing `manage_camera.py` through the SSH tunnel.

**Major:**
- **Remote viewing:**
  - View the camera stream remotely:
    - Start via an external server, since most users will run the app behind NAT.
    - Later, implement P2P streaming with NAT traversal techniques.

---
