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

### End of Version 2.0 Changelog

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

### End of Version 2.0.1 Changelog

---

### Version 2.0.2

**Implemented:**  
- View the camera stream remotely.  
- Start via an external server, since most users will run the app behind NAT.  
- More testing of multiple functionalities running simultaneously.

**Scrapped:**  
- Add a reverse SSH tunnel to a remote public server.  
- Get `server_view.py` running on the server and accessing `manage_camera.py` through the SSH tunnel.

**Detailed changes:**  
- Removed the TV fuzz idle feature — using unnecessary CPU/bandwidth on VPS.  
- Renamed `server_view.py` to `server_process.py`.  
- NAT circumvention + remote streaming added using raw TCP for now.  
- Changed `server_process.py` to receive socket connections (server socket), not initiate them.  
- Changed `manage_camera.py` to create socket OUT to `server_process.py`.  
- `manage_camera.py` now starts separate threads:  
  - 1 for local streaming,  
  - 1 for VPS streaming,  
  - 1 master socket listener.  
- Currently all pure TCP — sockets, signalling, and data. All unencrypted.  
- Significant research done on future pathways for streaming/connectivity remotely — protocol options, etc. See changelog 2.0.2 and new note: **"SSH tunneling, UDP streaming protocols.txt"**.

---

**To Run:**  
1. Run the GUI, click **"Show Camera Stream"** to start `manage_camera.py` etc.  
2. Open the web app at [http://146.190.96.130:1705/](http://146.190.96.130:1705/) and wait for the **"Desktop Connected"** message.  
3. Click **"Start"** button on the webpage to see the stream currently showing on the desktop app also appear in the browser.

*To run locally:*  
- Change `"server_host"` value in `manage_camera.py` to a loopback address (e.g., `127.0.0.1`).  
- Run `server_process.py`.  
- Open the web app locally at [http://127.0.0.1:1705/](http://127.0.0.1:1705/).

---

**Notes:**  
- Originally planned to establish a reverse SSH tunnel between PC and VPS upon app launch, enabling the same TCP socket code to work as if the app were completely local.  
- The idea was for `server_process.py` (fka. `server_view.py`) to initiate the socket inward when needed, circumventing NAT via the tunnel.  
- Discovered SSH tunneling is cumbersome and overkill for this case.  
- Restructured `server_process.py` from initiating socket (`client_socket.connect((host, port))`) to receiving socket connection (`server_socket.accept()`).  
- No initiation from PC outward; keep socket open awaiting commands and send video data back through that socket.  
- Entirely TCP-based and manual.  
- Significant research done on streaming protocols for PC → VPS and VPS → Browser, which was complex.

***For full details, see the new note in the Notes directory titled:  
"SSH tunneling, UDP streaming protocols.txt"***

---

#### Next Steps / TO DO:

**Minor:**  
- Change to long polling in JavaScript.  
- Remove pickle usage for server to improve speed (unnecessary for this setup; more details forthcoming).  
- Implement stop functionality from `server_process.py` HTML.  
- Add TLS encryption to sockets.  
- Make `client_socket.sendall` asynchronous with `asyncio`.  
- Eventually add WebSocket support browser ↔ server.

**Major:**  
- **Remote viewing:**  
  - Later, implement P2P streaming with NAT traversal techniques.

### End of Version 2.0.2 Changelog

---
