"""Wi-Fi configuration helpers; normal Wi-Fi is never reconfigured here."""
import json
import os
from pathlib import Path
import re
import secrets
import tempfile

from .process_utils import bounded_run


def run(*args):
    return bounded_run(args, timeout=15)


def channel_from_link(text):
    frequency = re.search(r"^\s*freq:\s*(\d+)(?:\.\d+)?", text, re.M)
    bssid = re.search(r"^Connected to ([\da-fA-F:]+)", text)
    if not frequency or not bssid:
        raise RuntimeError("Wi-Fi is not connected")
    mhz = int(frequency[1])
    if not 2412 <= mhz <= 2472 or (mhz - 2407) % 5:
        raise RuntimeError("Waiting for a normal Wi-Fi connection on 2.4 GHz; no band will be changed")
    return {"frequency": mhz, "channel": (mhz - 2407) // 5, "bssid": bssid[1].lower()}


def network_state(interface):
    state = run("nmcli", "-g", "GENERAL.STATE", "device", "show", interface)
    uuid = run("nmcli", "-g", "GENERAL.CON-UUID", "device", "show", interface)
    return int(state.split()[0]), uuid


def connected_network(config):
    requested = config["interface"]
    candidates = [requested] if requested else []
    if requested is None:
        for line in run("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device").splitlines():
            fields = line.split(":")
            if len(fields) == 3 and fields[1:] == ["wifi", "connected"] and fields[0] != config["ap_interface"]:
                candidates.append(fields[0])
    error = "Waiting for NetworkManager to connect normal Wi-Fi on 2.4 GHz"
    for interface in candidates:
        try:
            state, uuid = network_state(interface)
            if state == 100:
                link = channel_from_link(run("iw", "dev", interface, "link"))
                return {"interface": interface, "uuid": uuid, **link}
        except (RuntimeError, ValueError) as exc:
            error = str(exc)
    raise RuntimeError(error)


def still_connected(connection):
    interface = connection["interface"]
    state, uuid = network_state(interface)
    if (state, uuid) != (100, connection["uuid"]):
        return False
    link = channel_from_link(run("iw", "dev", interface, "link"))
    return all(link[key] == connection[key] for key in ("channel", "frequency", "bssid"))


def p2p_advertisement(mac):
    address = bytes.fromhex(mac.replace(":", ""))
    if len(address) != 6:
        raise ValueError("Invalid interface MAC address")
    def attribute(number, value):
        return bytes([number]) + len(value).to_bytes(2, "little") + value
    name = b"Open FatShield"
    info = (address + b"\x00\x80" + bytes.fromhex("00010050f2040001") + b"\x00" +
            b"\x10\x11" + len(name).to_bytes(2, "big") + name)
    body = (bytes.fromhex("506f9a09") + attribute(2, b"\x25\x09") + attribute(3, address) +
            attribute(13, info) + attribute(14, b""))
    return (b"\xdd" + bytes([len(body)]) + body).hex()


def hostapd_config(interface, control, channel, identity):
    return (f"interface={interface}\ndriver=nl80211\nctrl_interface={control}\n"
            f"ssid={identity['ssid']}\nhw_mode=g\nchannel={channel}\n"
            "supported_rates=60 90 120 180 240 360 480 540\nbasic_rates=60 120 240\n"
            "wmm_enabled=1\nauth_algs=1\nwpa=2\nwpa_key_mgmt=WPA-PSK\nrsn_pairwise=CCMP\n"
            f"wpa_passphrase={identity['passphrase']}\n"
            "eap_server=1\nwps_state=2\nap_setup_locked=0\nconfig_methods=push_button\n"
            "device_name=Open FatShield\ndevice_type=1-0050F204-1\n"
            "manufacturer=Linux\nmodel_name=SHIELD-Controller\n"
            f"vendor_elements={p2p_advertisement(identity['mac'])}\n")


def atomic_json(path, value, mode=0o600):
    path = Path(path)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(temporary_name)
    os.fchmod(descriptor, mode)
    try:
        with os.fdopen(descriptor, "w") as file:
            json.dump(value, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_identity(path):
    if not path.exists():
        return None
    identity = json.loads(path.read_text())
    if set(identity) != {"ssid", "passphrase", "mac"}:
        raise ValueError("Invalid saved controller network; restore the local network.json backup")
    if not re.fullmatch(r"DIRECT-SHIELD-[a-f0-9]{6}", identity["ssid"]):
        raise ValueError("Invalid saved controller SSID")
    if not re.fullmatch(r"[a-f0-9]{32}", identity["passphrase"]):
        raise ValueError("Invalid saved controller network key")
    if not re.fullmatch(r"(?:[a-fA-F0-9]{2}:){5}[a-fA-F0-9]{2}", identity["mac"]):
        raise ValueError("Invalid saved controller interface address")
    return identity


def new_identity(mac):
    return {"ssid": "DIRECT-SHIELD-" + secrets.token_hex(3),
            "passphrase": secrets.token_hex(16), "mac": mac}
