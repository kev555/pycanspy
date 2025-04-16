import time
import servicemanager
import win32event
import win32service
import win32serviceutil
import record_cam  # Import your script


class MyService(win32serviceutil.ServiceFramework):
    _svc_name_ = "ZZZMyPythonService"
    _svc_display_name_ = "My Python Background Service (5-Minute Run)"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("ZZZMyPythonService is starting...")

        # Start your script
        try:
            record_cam.main()
        except Exception as e:
            servicemanager.LogErrorMsg(f"Error running record_cam: {e}")

        # Wait for x minutes or until service is stopped
        wait_time = 0
        while self.running and wait_time < 350:
            time.sleep(1)
            wait_time += 1

        servicemanager.LogInfoMsg("ZZZMyPythonService has stopped after x minutes.")

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(MyService)
