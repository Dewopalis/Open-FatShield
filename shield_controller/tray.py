"""Qt system tray and controller window; administrator actions stay in the CLI."""
import fcntl
import json
import os
from pathlib import Path
import sys

from .cli import ensure_agent

COLORS = {"connected": "#39b969", "ready": "#509deb", "starting": "#edb442",
          "waiting": "#edb442", "kernel_fault": "#ed645a", "stopped": "#8a939e"}
TITLES = {"connected": "Controller connected", "ready": "Ready to connect",
          "starting": "Starting", "waiting": "Waiting for Wi-Fi",
          "kernel_fault": "Driver fault", "stopped": "Disconnected"}


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Run the tray application as your normal desktop user")
    try:
        from PySide6.QtCore import QProcess, QTimer, Qt
        from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
                                      QMenu, QPushButton, QSystemTrayIcon,
                                      QVBoxLayout, QWidget)
    except ImportError:
        raise RuntimeError("Install PySide6 for the system tray: sudo pacman -S pyside6")
    app = QApplication([sys.argv[0]])
    app.setApplicationName("SHIELD Controller")
    app.setQuitOnLastWindowClosed(False)
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    lock = (runtime / "shield-controller-tray.lock").open("w")
    server_name = "shield-controller-tray-" + str(os.getuid())
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        client = QLocalSocket()
        client.connectToServer(server_name)
        if client.waitForConnected(1000):
            client.write(b"show")
            client.waitForBytesWritten(1000)
        return
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(server_name):
        raise RuntimeError("Could not create the tray application socket")
    ensure_agent()
    executable = "/usr/bin/shield-controller"

    def icon(state):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#dae1e8"), 3))
        painter.setBrush(QColor("#303943"))
        painter.drawRoundedRect(5, 16, 53, 35, 12, 12)
        painter.drawLine(15, 32, 29, 32)
        painter.drawLine(22, 25, 22, 39)
        painter.setBrush(QColor("#dae1e8"))
        painter.drawEllipse(39, 27, 5, 5)
        painter.drawEllipse(47, 34, 5, 5)
        painter.setPen(QPen(QColor("#20272e"), 2))
        painter.setBrush(QColor(COLORS.get(state, COLORS["waiting"])))
        painter.drawEllipse(42, 43, 18, 18)
        painter.end()
        return QIcon(pixmap)

    window = QWidget()
    window.setWindowTitle("SHIELD Controller")
    window.setMinimumWidth(390)
    layout = QVBoxLayout(window)
    title = QLabel("Checking controller…")
    title.setStyleSheet("font-size: 20px; font-weight: 600; margin-top: 8px")
    details = QLabel()
    details.setWordWrap(True)
    details.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(title)
    layout.addWidget(details)
    buttons = QHBoxLayout()
    layout.addLayout(buttons)
    pair_button = QPushButton("Pair controller")
    connect_button = QPushButton("Connect")
    disconnect_button = QPushButton("Disconnect")
    for button in (pair_button, connect_button, disconnect_button):
        buttons.addWidget(button)
    boot = QCheckBox("Start controller service automatically at boot")
    layout.addWidget(boot)
    hint = QLabel("Normal Wi-Fi must use 2.4 GHz. Pairing requires unplugging USB and holding the NVIDIA button until it flashes.")
    hint.setWordWrap(True)
    layout.addWidget(hint)
    message = QLabel()
    message.setWordWrap(True)
    message.setTextFormat(Qt.TextFormat.PlainText)
    layout.addWidget(message)
    hide = QPushButton("Hide to tray")
    layout.addWidget(hide)
    hide.clicked.connect(window.hide)
    tray = QSystemTrayIcon(icon("stopped"), app)
    menu = QMenu()
    status_action = menu.addAction("Checking controller…")
    status_action.setEnabled(False)
    menu.addSeparator()
    show_action = menu.addAction("Open controller window")
    pair_action = menu.addAction("Pair controller…")
    connect_action = menu.addAction("Connect")
    disconnect_action = menu.addAction("Disconnect")
    menu.addSeparator()
    boot_action = menu.addAction("Start service at boot")
    boot_action.setCheckable(True)
    menu.addSeparator()
    quit_action = menu.addAction("Quit tray application")
    tray.setContextMenu(menu)

    def show_window():
        window.show()
        window.raise_()
        window.activateWindow()

    show_action.triggered.connect(show_window)
    quit_action.triggered.connect(app.quit)
    tray.activated.connect(lambda reason: show_window() if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                                                                    QSystemTrayIcon.ActivationReason.DoubleClick) else None)

    def incoming():
        client = server.nextPendingConnection()
        if client is not None:
            client.disconnectFromServer()
            client.deleteLater()
            show_window()
    server.newConnection.connect(incoming)
    action_process = QProcess(app)
    status_process = QProcess(app)
    boot_process = QProcess(app)
    pending_action = [None]
    current_state = [None]
    actions = (pair_action, connect_action, disconnect_action, boot_action)
    widgets = (pair_button, connect_button, disconnect_button, boot)

    def busy(value):
        for control in actions + widgets + (quit_action,):
            control.setEnabled(not value)

    def act(command):
        if action_process.state() != QProcess.ProcessState.NotRunning:
            return
        pending_action[0] = command
        message.setText("Waiting for administrator authorization…")
        busy(True)
        action_process.start(executable, [command])

    def action_finished(code, exit_status):
        busy(False)
        text = bytes(action_process.readAllStandardOutput()).decode(errors="replace").strip()
        error = bytes(action_process.readAllStandardError()).decode(errors="replace").strip()
        if code:
            message.setText(error or text or "The action did not complete.")
            show_window()
        else:
            message.setText(text or "Done")
            if pending_action[0] == "pair":
                show_window()
                tray.showMessage("SHIELD pairing", "Unplug USB and hold the NVIDIA button until it flashes. Pairing is open for two minutes.")
        refresh()

    action_process.finished.connect(action_finished)
    def failed_to_start(error):
        if error == QProcess.ProcessError.FailedToStart:
            busy(False)
            message.setText("Could not launch the installed shield-controller command")
            show_window()
    action_process.errorOccurred.connect(failed_to_start)
    pair_action.triggered.connect(lambda: act("pair"))
    connect_action.triggered.connect(lambda: act("start"))
    disconnect_action.triggered.connect(lambda: act("stop"))
    boot_action.triggered.connect(lambda checked: act("enable" if checked else "disable"))
    pair_button.clicked.connect(lambda: act("pair"))
    connect_button.clicked.connect(lambda: act("start"))
    disconnect_button.clicked.connect(lambda: act("stop"))
    boot.clicked.connect(lambda checked: act("enable" if checked else "disable"))

    def update_status(code, exit_status):
        try:
            if code:
                raise ValueError("Status command failed")
            status = json.loads(bytes(status_process.readAllStandardOutput()).decode())
        except (ValueError, UnicodeError):
            status = {"state": "waiting", "message": "Could not read service status"}
        state = status.get("state", "waiting")
        label = TITLES.get(state, "Checking controller")
        description = status.get("message", "")
        if "channel" in status:
            description += f"\nWi-Fi: {status['interface']} · channel {status['channel']} · {status.get('input_events', 0)} input events"
        title.setText(label)
        details.setText(description)
        status_action.setText(label)
        tray.setToolTip("SHIELD Controller — " + label)
        if current_state[0] != state:
            tray.setIcon(icon(state))
            window.setWindowIcon(icon(state))
            if current_state[0] is not None and state == "connected":
                tray.showMessage("SHIELD Controller", "Controller connected")
            current_state[0] = state

    status_process.finished.connect(update_status)
    def update_boot(code, exit_status):
        enabled = code == 0
        boot.setChecked(enabled)
        boot_action.setChecked(enabled)
    boot_process.finished.connect(update_boot)

    def refresh():
        if status_process.state() == QProcess.ProcessState.NotRunning:
            status_process.start(executable, ["status", "--json"])
        if boot_process.state() == QProcess.ProcessState.NotRunning:
            boot_process.start("systemctl", ["is-enabled", "--quiet", "shield-controller.service"])
    timer = QTimer(app)
    timer.setInterval(3000)
    timer.timeout.connect(refresh)
    timer.start()
    refresh()
    tray.show()
    if (len(sys.argv) > 1 and sys.argv[1] == "gui") or not QSystemTrayIcon.isSystemTrayAvailable():
        show_window()
    app.exec()
    server.close()
    QLocalServer.removeServer(server_name)
    lock.close()
