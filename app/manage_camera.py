import cv2
import threading
import win32pipe, win32file, pywintypes

pipe_name = r'\\.\pipe\recordcam_pipe'
show_stream = False
recording = False
writer = None

def handle_commands():
    global show_stream, recording, writer

    while True:
        print("[*] Waiting for GUI to connect to pipe...")
        pipe = win32pipe.CreateNamedPipe(
            pipe_name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536,
            0,
            None
        )

        try:
            win32pipe.ConnectNamedPipe(pipe, None)
            print("[*] GUI connected to pipe.")

            while True:
                try:
                    result, data = win32file.ReadFile(pipe, 64 * 1024)
                    cmd = data.decode().strip()
                    print(f"[>] Received command: {cmd}")

                    if cmd == "show_stream":
                        show_stream = True
                    elif cmd == "hide_stream":
                        show_stream = False
                    elif cmd == "start_record":
                        recording = True
                    elif cmd == "stop_record":
                        recording = False
                        if writer:
                            writer.release()
                            writer = None
                    elif cmd == "exit":
                        print("[*] Exiting command handler.")
                        return
                except pywintypes.error as e:
                    print(f"[!] Error reading from pipe: {e}")
                    break

        finally:
            win32file.CloseHandle(pipe)

def camera_loop():
    global writer
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("[!] Could not open webcam.")
        return

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if show_stream:
            cv2.imshow("Live", frame)
            if cv2.waitKey(1) == 27:
                break
        else: # Only destroy if window exists
            if not recording:
                try:
                    cap.release()
                    cv2.destroyWindow("Live")
                except:
                    pass
            

        if recording:
            if writer is None:
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                writer = cv2.VideoWriter("output.avi", fourcc, 20.0, (640, 480))
            writer.write(frame)

    cap.release()
    if writer:
        writer.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    threading.Thread(target=handle_commands, daemon=True).start()
    camera_loop()
