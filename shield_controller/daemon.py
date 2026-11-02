import os
import fcntl
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from .config import RUNTIME, STATE, RULE, load_config
from .input_monitor import InputMonitor
from .network import atomic_json, connected_network, hostapd_config, load_identity, new_identity, run, still_connected
from .process_utils import bounded_run, stop_owned_process


class KernelFault(RuntimeError):
    pass


def kernel_faults(since):
    try:
        return run("journalctl", "-k", "--since", since, "--no-pager", "-o", "cat",
                   "--grep", "Oops:|kernel BUG|memcpy: detected buffer overflow|BUG: KASAN")
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 1 and (exc.output or "").strip() in ("", "-- No entries --"):
            return ""
        raise


def recover_owned_resources():
    ownership = RUNTIME / "ownership.json"
    if not ownership.exists():
        return
    from .config import interface_name
    record = json.loads(ownership.read_text())
    ap_interface = interface_name(record["ap_interface"])
    if ap_interface == record.get("parent_interface"):
        raise RuntimeError("Invalid ownership record; refusing to remove the normal Wi-Fi interface")
    errors = []
    if record.get("module") and Path("/sys/module/ozwpan").exists():
        try:
            run("modprobe", "-r", "ozwpan")
        except Exception as exc:
            errors.append(str(exc))
    if record.get("interface") and Path("/sys/class/net", ap_interface).exists():
        try:
            run("iw", "dev", ap_interface, "del")
        except Exception as exc:
            errors.append(str(exc))
    if record.get("rule") and RULE.exists():
        expected = f"[device-shield-controller]\nmatch-device=interface-name:{ap_interface}\nmanaged=0\n"
        if RULE.read_text() != expected:
            errors.append("Runtime NM rule changed; refusing to delete it")
        else:
            RULE.unlink()
            run("nmcli", "general", "reload", "conf")
    if errors:
        raise RuntimeError("Cleanup incomplete: " + "; ".join(errors))
    ownership.unlink(missing_ok=True)


class ControllerDaemon:
    def __init__(self, config):
        self.config = config
        self.stopping = False
        self.last_status = None

    def stop(self, signum=None, frame=None):
        self.stopping = True

    def status(self, state, message, **fields):
        value = {"state": state, "message": message, "updated_at": time.time(), **fields}
        atomic_json(RUNTIME / "status.json", value, mode=0o644)
        current = (state, message)
        if current != self.last_status:
            print(message, flush=True)
            self.last_status = current

    def session(self, connection):
        ap_interface = self.config["ap_interface"]
        if Path("/sys/class/net", ap_interface).exists() or RULE.exists():
            raise RuntimeError("Controller interface/rule already exists; stop the other controller session first")
        if Path("/sys/module/ozwpan").exists():
            raise RuntimeError("ozwpan is already loaded by another session")
        saved = load_identity(STATE / "network.json")
        monitor = ap = None
        loaded = rule_owned = interface_owned = False
        ownership = {"ap_interface": ap_interface, "parent_interface": connection["interface"],
                     "rule": False, "interface": False, "module": False}
        with tempfile.TemporaryDirectory(prefix="ap-", dir=RUNTIME) as directory:
            temporary = Path(directory)
            control = RUNTIME / "hostapd"
            control.mkdir(mode=0o700, exist_ok=True)
            try:
                self.status("starting", "Starting the controller access point", interface=connection["interface"])
                RULE.parent.mkdir(parents=True, exist_ok=True)
                with RULE.open("x") as rule:
                    rule_owned = True
                    rule.write(f"[device-shield-controller]\nmatch-device=interface-name:{ap_interface}\nmanaged=0\n")
                ownership["rule"] = True
                atomic_json(RUNTIME / "ownership.json", ownership)
                run("nmcli", "general", "reload", "conf")
                command = ["iw", "dev", connection["interface"], "interface", "add", ap_interface, "type", "__ap"]
                if saved:
                    command += ["addr", saved["mac"]]
                run(*command)
                interface_owned = True
                ownership["interface"] = True
                atomic_json(RUNTIME / "ownership.json", ownership)
                mac = Path("/sys/class/net", ap_interface, "address").read_text().strip()
                identity = saved or new_identity(mac)
                if not saved:
                    atomic_json(STATE / "network.json", identity)
                config_path = temporary / "hostapd.conf"
                config_path.write_text(hostapd_config(ap_interface, control, connection["channel"], identity))
                config_path.chmod(0o600)
                # No debug/key-dump flags; normal hostapd events go to the journal.
                ap = subprocess.Popen(["hostapd", "-t", str(config_path)])
                def ap_cli(*arguments):
                    output = run("hostapd_cli", "-s", str(control), "-p", str(control), "-i", ap_interface, *arguments)
                    if "FAIL" in output:
                        raise RuntimeError(f"Controller AP command {arguments[0]} failed")
                    return output
                for _ in range(50):
                    if self.stopping:
                        return
                    if ap.poll() is not None:
                        raise RuntimeError("Controller AP exited; inspect shield-controller logs")
                    if (control / ap_interface).exists() and "state=ENABLED" in ap_cli("status"):
                        break
                    time.sleep(0.2)
                else:
                    raise RuntimeError("Controller AP did not become ready")
                if not still_connected(connection):
                    raise RuntimeError("Normal Wi-Fi changed during setup; controller AP will be removed")
                run("modprobe", "ozwpan", f"g_net_dev={ap_interface}")
                loaded = True
                ownership["module"] = True
                atomic_json(RUNTIME / "ownership.json", ownership)
                monitor = InputMonitor()
                initialized = set()
                next_health = 0
                next_status = 0
                kernel_start = time.strftime("%Y-%m-%d %H:%M:%S")
                while not self.stopping:
                    if ap.poll() is not None:
                        raise RuntimeError("Controller AP stopped")
                    if time.monotonic() >= next_health:
                        if not still_connected(connection):
                            return  # Recreate only the controller AP for the new Wi-Fi channel.
                        kernel = kernel_faults(kernel_start)
                        if any(marker in kernel for marker in ("Oops:", "kernel BUG", "memcpy: detected buffer overflow", "BUG: KASAN")):
                            raise KernelFault("Kernel fault detected; controller service stopped. Reboot may be required.")
                        kernel_start = time.strftime("%Y-%m-%d %H:%M:%S")
                        next_health = time.monotonic() + 5
                    monitor.discover(Path("/proc/bus/input/devices").read_text())
                    monitor.poll()
                    if monitor.devices:
                        for node in sorted(Path("/sys/class/hidraw").glob("hidraw*")):
                            target = str((node / "device").resolve())
                            if "/devices/platform/ozwpan/" not in target or target in initialized:
                                continue
                            initialized.add(target)
                            output = bounded_run((sys.executable, str(Path(__file__).with_name("get_input_reports.py")),
                                                  "/dev/" + node.name), timeout=15)
                            print("Controller input initialization completed", flush=True)
                    if time.monotonic() >= next_status:
                        self.status("connected" if monitor.devices else "ready",
                                    "Controller connected" if monitor.devices else "Ready; use Pair for a new controller",
                                    interface=connection["interface"], ap_interface=ap_interface,
                                    channel=connection["channel"], input_events=monitor.count)
                        next_status = time.monotonic() + 1
                    time.sleep(0.1)
            finally:
                actions = []
                if monitor is not None:
                    actions.append(("input reader", monitor.close))
                if loaded:
                    actions.append(("driver", lambda: run("modprobe", "-r", "ozwpan")))
                if ap is not None:
                    actions.append(("controller AP", lambda: stop_owned_process(ap)))
                if interface_owned:
                    actions.append(("virtual interface", lambda: run("iw", "dev", ap_interface, "del")))
                if rule_owned:
                    actions.append(("temporary NM rule", RULE.unlink))
                    actions.append(("NM configuration reload", lambda: run("nmcli", "general", "reload", "conf")))
                failed = False
                for name, action in actions:
                    try:
                        action()
                    except Exception as exc:
                        failed = True
                        print(f"Cleanup of {name} failed: {exc}", flush=True)
                if not failed:
                    (RUNTIME / "ownership.json").unlink(missing_ok=True)

    def serve(self):
        RUNTIME.mkdir(mode=0o755, parents=True, exist_ok=True)
        STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(STATE, 0o700)
        lock = (RUNTIME / "daemon.lock").open("w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another controller daemon is already running")
        recover_owned_resources()
        if (RUNTIME / "kernel-fault").exists():
            self.status("kernel_fault", "Previous kernel fault detected; reboot before starting again")
            return
        while not self.stopping:
            try:
                connection = connected_network(self.config)
                self.session(connection)
            except KernelFault as exc:
                (RUNTIME / "kernel-fault").touch(mode=0o600)
                self.status("kernel_fault", str(exc))
                return
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
                self.status("waiting", str(exc))
            for _ in range(30):
                if self.stopping:
                    break
                time.sleep(0.1)
        self.status("stopped", "Controller service stopped")


def main():
    if os.geteuid() != 0:
        raise SystemExit("The controller daemon must run as root through its system service")
    daemon = ControllerDaemon(load_config())
    signal.signal(signal.SIGTERM, daemon.stop)
    signal.signal(signal.SIGINT, daemon.stop)
    daemon.serve()
