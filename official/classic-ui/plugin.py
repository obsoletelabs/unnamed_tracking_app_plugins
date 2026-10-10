"""Classic UI is presentation-only; the host owns all application behavior."""
import time

from sdk.plugin_protocol import request


def main() -> None:
    request("lifecycle.ready", "lifecycle.ready", {})
    while True:
        time.sleep(3600)
