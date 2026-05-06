import sys
import os

addon_id = "plugin.audio.pandora"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "resources", "lib"))

try:
    import xbmc
except ImportError:
    pass

def klog(msg):
    try:
        xbmc.log(f"[PANDORA] {msg}", xbmc.LOGINFO)
    except:
        pass

class PandoraMonitor(xbmc.Player):
    def onPlayBackEnded(self):
        pass

def run_service():
    monitor = PandoraMonitor()
    monitor_mk = xbmc.Monitor()
    while not monitor_mk.abortRequested():
        monitor_mk.waitForAbort(1)

if __name__ == "__main__":
    run_service()
