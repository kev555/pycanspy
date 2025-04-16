import cv2
import datetime
import os
import time
import traceback

clip_intervals = 10

try:
    # Set the output directory to Downloads > recordings
    output_dir = os.path.expanduser("C:/Users/kevw/Downloads/Recording from Webcam/recordings")
    os.makedirs(output_dir, exist_ok=True)

    # Open webcam (check if the camera is available)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise Exception("Could not open video device. Make sure your camera is connected and available.")

    print("Camera initialized successfully.")

    # Initialize video writer and timestamp
    fourcc = cv2.VideoWriter_fourcc(*'XVID')

    while cap.isOpened():
        # Create a new filename for each 10-second segment
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"webcam_{timestamp}.avi")
        out = cv2.VideoWriter(output_file, fourcc, 20.0, (640, 480))
        
        # Record for x seconds
        start_time = time.time()
        while time.time() - start_time < clip_intervals:
            ret, frame = cap.read()
            if ret:
                out.write(frame)
            else:
                print("Failed to capture frame.")
                break

        # Release the current video writer after 10 seconds and start a new file
        out.release()
        print(f"File {output_file} saved.")

    cap.release()

except Exception as e:
    # Log any errors
    error_log = os.path.join(output_dir, "webcam_error.log")
    with open(error_log, "w") as f:
        f.write(traceback.format_exc())
    print("An error occurred. See webcam_error.log for details.")
