import time

try:
    print("Running. Press Ctrl+C to stop.")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopped by Ctrl+C")
