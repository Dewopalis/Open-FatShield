"""Open and observe only the virtual SHIELD controller's evdev input nodes."""
import json
import os
from pathlib import Path
import re
import struct
import time

INPUT_EVENT = struct.Struct("@llHHi")


def wireless_nodes(devices):
    nodes = {}
    for block in devices.split("\n\n"):
        if "Vendor=0955 Product=7210" not in block:
            continue
        if "Phys=usb-ozwpan-" not in block and "/devices/platform/ozwpan/" not in block:
            continue
        name = re.search(r'^N: Name="(.*)"$', block, re.M)
        handlers = re.search(r"^H: Handlers=(.*)$", block, re.M)
        if not handlers:
            continue
        for event in re.findall(r"\bevent\d+\b", handlers.group(1)):
            nodes["/dev/input/" + event] = name.group(1) if name else "SHIELD"
    return nodes


class InputMonitor:
    def __init__(self, log_path=None, media_handler=None, verbose=False):
        self.devices = {}
        self.log = Path(log_path).open("x") if log_path is not None else None
        self.verbose = verbose
        self.count = 0
        self.printed = 0
        self.media_handler = media_handler
        self.retry_at = {}

    def discover(self, devices):
        for path, name in wireless_nodes(devices).items():
            if path in self.devices:
                continue
            if time.monotonic() < self.retry_at.get(path, 0):
                continue
            try:
                descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            except OSError as exc:
                print(f"Could not open {path}: {exc}", flush=True)
                self.retry_at[path] = time.monotonic() + 3
                continue
            self.devices[path] = descriptor
            print(f"Listening for input on {path}: {name}.", flush=True)

    def poll(self):
        for path, descriptor in list(self.devices.items()):
            for _ in range(16):
                try:
                    data = os.read(descriptor, INPUT_EVENT.size * 128)
                except BlockingIOError:
                    break
                except OSError as exc:
                    print(f"Input reader stopped on {path}: {exc}", flush=True)
                    os.close(descriptor)
                    del self.devices[path]
                    break
                if not data:
                    break
                for seconds, micros, event_type, code, value in INPUT_EVENT.iter_unpack(data):
                    if event_type not in (1, 2, 3):
                        continue
                    event = {"device": path, "seconds": seconds, "microseconds": micros,
                             "type": event_type, "code": code, "value": value}
                    if self.log is not None:
                        self.log.write(json.dumps(event) + "\n")
                    self.count += 1
                    if self.media_handler is not None:
                        self.media_handler.handle(event_type, code, value)
                    if self.verbose and self.printed < 30:
                        print(f"INPUT {path}: type={event_type} code={code} value={value}", flush=True)
                        self.printed += 1
            if self.log is not None:
                self.log.flush()

    def close(self):
        for descriptor in self.devices.values():
            os.close(descriptor)
        self.devices.clear()
        if self.log is not None:
            self.log.close()
        print(f"Recorded {self.count} button/axis/mouse events from wireless SHIELD devices.", flush=True)
