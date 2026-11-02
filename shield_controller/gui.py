import shutil
import subprocess

from .cli import ensure_agent, read_status, root_action, run

ACTIONS = {"pair": "Pair controller", "start": "Start", "stop": "Stop",
           "status": "Refresh status", "enable": "Start automatically at boot",
           "disable": "Disable automatic startup"}


def main():
    if not shutil.which("kdialog") and not shutil.which("zenity"):
        raise RuntimeError("Install kdialog (KDE) or zenity (GTK) for the desktop window, or use the CLI")
    ensure_agent()
    kde = bool(shutil.which("kdialog"))
    while True:
        message = read_status()["message"] + "\n\nGamepad, touchpad and volume over Wi-Fi. Normal Wi-Fi must use 2.4 GHz."
        if kde:
            command = ["kdialog", "--title", "SHIELD Controller", "--menu", message]
            for key, label in ACTIONS.items():
                command += [key, label]
        else:
            command = ["zenity", "--list", "--title=SHIELD Controller", "--text=" + message,
                       "--column=Action", "--column=Description", "--hide-column=1", "--print-column=1"]
            for key, label in ACTIONS.items():
                command += [key, label]
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE)
        if result.returncode:
            return
        action = result.stdout.strip()
        if action == "status":
            continue
        if action not in ACTIONS:
            continue
        try:
            root_action(action)
            if action == "pair":
                text = "Unplug USB and hold the NVIDIA button until it flashes.\nPairing stays open for two minutes."
            else:
                text = read_status()["message"]
            if kde:
                subprocess.run(["kdialog", "--title", "SHIELD Controller", "--msgbox", text])
            else:
                subprocess.run(["zenity", "--info", "--title=SHIELD Controller", "--text=" + text])
        except Exception as exc:
            if kde:
                subprocess.run(["kdialog", "--title", "SHIELD Controller", "--error", str(exc)])
            else:
                subprocess.run(["zenity", "--error", "--title=SHIELD Controller", "--text=" + str(exc)])
