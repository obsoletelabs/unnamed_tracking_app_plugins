"""Owner-only credential file keyed by instance ID (never in URLs or logs)."""

from __future__ import annotations

import json
import os
from pathlib import Path


class CredentialStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def save(self, instance_id: str, token: str, grant_id: str) -> None:
        data = self._read()
        data[instance_id] = {"token": token, "grant_id": grant_id}
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        os.chmod(self.path, 0o600)

    def load(self, instance_id: str) -> dict | None:
        return self._read().get(instance_id)

    def forget(self, instance_id: str) -> None:
        data = self._read()
        if data.pop(instance_id, None) is not None:
            self.path.write_text(json.dumps(data), encoding="utf-8")
