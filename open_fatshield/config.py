import json
from pathlib import Path
import re

CONFIG_PATH = Path("/etc/open-fatshield/config.json")
RUNTIME = Path("/run/open-fatshield")
STATE = Path("/var/lib/open-fatshield")
RULE = Path("/run/NetworkManager/conf.d/90-open-fatshield.conf")
DEFAULTS = {"interface": None, "ap_interface": "shield0"}


def interface_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,15}", value):
        raise ValueError("Interface names must be 1–15 letters, digits, underscores or hyphens")
    return value


def load_config(path=CONFIG_PATH):
    config = dict(DEFAULTS)
    if path.exists():
        supplied = json.loads(path.read_text())
        if not isinstance(supplied, dict) or set(supplied) - set(DEFAULTS):
            raise ValueError("Unknown configuration keys; use interface and ap_interface")
        config.update(supplied)
    interface_name(config["ap_interface"])
    if config["interface"] is not None:
        interface_name(config["interface"])
        if config["interface"] == config["ap_interface"]:
            raise ValueError("Normal Wi-Fi and controller interfaces must differ")
    return config
