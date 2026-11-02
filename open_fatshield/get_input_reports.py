"""Read HID input reports 1 and 2 from the virtual wireless SHIELD only."""
import argparse
import fcntl
import os
from pathlib import Path
import re


def read_reports(descriptor):
    results = []
    for report_id in (1, 2):
        data = bytearray(65)
        data[0] = report_id
        # HIDIOCGINPUT(65), from the host's linux/hidraw.h. This ioctl's
        # bidirectional user buffer does not send a HID SET_REPORT operation.
        request = (3 << 30) | (len(data) << 16) | (ord("H") << 8) | 0x0A
        try:
            size = fcntl.ioctl(descriptor, request, data, True)
            result = {"report_id": report_id, "length": size,
                      "data": bytes(data[:max(0, min(size, len(data)))]).hex()}
        except OSError as exc:
            result = {"report_id": report_id, "error": str(exc)}
        results.append(result)
        print(result, flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device")
    args = parser.parse_args()
    if not re.fullmatch(r"/dev/hidraw\d+", args.device):
        parser.error("Expected an absolute /dev/hidrawN device path")
    device = (Path("/sys/class/hidraw") / Path(args.device).name / "device").resolve()
    if "/devices/platform/ozwpan/" not in str(device):
        parser.error("Refusing a device outside the virtual OZWPAN host controller")
    identity = (device / "uevent").read_text()
    match = re.search(r"^HID_ID=([\da-fA-F]+):([\da-fA-F]+):([\da-fA-F]+)$", identity, re.M)
    if not match or int(match[2], 16) != 0x0955 or int(match[3], 16) != 0x7210:
        parser.error("Device identity is not the original SHIELD controller")
    descriptor = os.open(args.device, os.O_RDONLY | os.O_NONBLOCK)
    try:
        read_reports(descriptor)
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    main()
