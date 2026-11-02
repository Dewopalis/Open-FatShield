"""Optional offscreen Qt smoke test, without host/service changes."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QByteArray, QProcess
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QSystemTrayIcon, QWidget
from open_fatshield import tray


def start(process, executable, arguments):
    process.setProperty("test_arguments", arguments)


def inspect(self=None):
    app = QApplication.instance()
    for process in app.findChildren(QProcess):
        if process.property("test_arguments") == ["status", "--json"]:
            process.finished.emit(0, QProcess.ExitStatus.NormalExit)
    window = next(w for w in app.topLevelWidgets() if w.windowTitle() == "Open FatShield")
    labels = [w.text() for w in window.findChildren(QLabel)]
    assert "Controller connected" in labels, labels
    buttons = {w.text() for w in window.findChildren(QPushButton)}
    assert {"Pair controller", "Connect", "Disconnect"} <= buttons
    window.show()
    app.processEvents()
    screenshot = Path(os.environ.get("SHIELD_TRAY_SCREENSHOT", "/tmp/open-fatshield-tray.png"))
    assert window.grab().save(str(screenshot))
    print("Qt tray/window smoke test passed: " + str(screenshot))
    return 0


status = {"state": "connected", "message": "Controller connected", "interface": "wlan0", "channel": 4, "input_events": 1286}
with tempfile.TemporaryDirectory() as runtime, \
     patch.dict(os.environ, {"XDG_RUNTIME_DIR": runtime}), \
     patch.object(tray, "ensure_agent"), \
     patch.object(QProcess, "start", start), \
     patch.object(QProcess, "readAllStandardOutput", return_value=QByteArray(json.dumps(status).encode())), \
     patch.object(QApplication, "exec", inspect), \
     patch.object(QSystemTrayIcon, "show"), \
     patch.object(QSystemTrayIcon, "showMessage"):
    tray.main()
