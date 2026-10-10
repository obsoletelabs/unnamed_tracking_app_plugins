"""Actual host/gateway setup for installed notification renderer conformance.

Only acceptance plumbing lives here. Host authorization, runtime HTTP, workers,
settings and storage remain the real implementations from the supplied host.
"""
from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import httpx


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def renderer_host(host_root: Path, registry, actor: str, plugin: str, installation: str):
    from runtime import RuntimeHandler, RuntimeServer

    host_port, runtime_port = _port(), _port()
    names = ("PLUGIN_RUNTIME_TOKEN", "PLUGIN_RUNTIME_URL", "PLUGIN_GATEWAY_URL")
    previous = {name: os.environ.get(name) for name in names}
    token = secrets.token_urlsafe(48)
    os.environ.update(PLUGIN_RUNTIME_TOKEN=token,
                      PLUGIN_RUNTIME_URL=f"http://127.0.0.1:{runtime_port}",
                      PLUGIN_GATEWAY_URL=f"http://127.0.0.1:{host_port}")
    supervisor = registry.supervisor
    old_gateway = (supervisor.gateway_url, supervisor.gateway_token,
                   supervisor.gateway_configuration_source)
    supervisor.gateway_token = token
    supervisor.gateway_url = os.environ["PLUGIN_GATEWAY_URL"]
    supervisor.gateway_configuration_source = "runtime"
    env = {**os.environ, "STARTUP_MODE": "testing", "DEBUG": "false",
           "PYTHONPATH": str(host_root / "src/backend"),
           "PLUGIN_MANAGER_STATE_PATH": str(registry.root / "renderer-manager.json")}
    seed = '''
import asyncio, sys
from uuid import UUID
from sqlalchemy import delete
from src.main import app
from src.database.session import SessionLocal, engine
from src.plugin_api.manager_state import manager_state
from src.database.models.user import User
from src.database.models.plugin_permissions import PluginPermissionGrant
from src.database.models.plugin_notification_provider import PluginNotificationProviderRegistration
async def run():
    actor, plugin, installation, cleanup = sys.argv[1:]
    manager_state().settings({"reduced_isolation_acknowledged": True})
    async with SessionLocal() as db:
        if cleanup == "yes":
            await db.execute(delete(PluginPermissionGrant).where(PluginPermissionGrant.plugin_id == plugin, PluginPermissionGrant.installation_id == UUID(installation)))
            await db.execute(delete(PluginNotificationProviderRegistration).where(PluginNotificationProviderRegistration.plugin_id == plugin, PluginNotificationProviderRegistration.installation_id == UUID(installation)))
            await db.execute(delete(User).where(User.id == UUID(actor)))
        else:
            db.add(User(id=UUID(actor), username=actor, email=actor+"@example.invalid", password_hash="unused"))
            await db.flush()
            for capability in ("plugin.settings", "plugin.storage", "notification_providers.register", "notification_providers.deliver"):
                db.add(PluginPermissionGrant(plugin_id=plugin, installation_id=UUID(installation), user_id=UUID(actor), capability=capability, capability_version=1))
        await db.commit()
    await engine.dispose()
asyncio.run(run())
'''
    server = RuntimeServer(("127.0.0.1", runtime_port), RuntimeHandler)
    server.registry = registry
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    process = None
    try:
        subprocess.run([sys.executable, "-c", seed, actor, plugin, installation, "no"],
                       env=env, check=True, capture_output=True, text=True)
        thread.start()
        log_path = registry.root / "notification-renderer-host.log"
        with log_path.open("w") as log:
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.main:app",
                                        "--host", "127.0.0.1", "--port", str(host_port)],
                                       cwd=host_root / "src/backend", env=env,
                                       stdout=log, stderr=log)
            deadline = time.monotonic() + 30
            while True:
                try:
                    response = httpx.get(os.environ["PLUGIN_GATEWAY_URL"] + "/api/auth/me", timeout=1)
                    if response.status_code in (200, 401, 404):
                        break
                except httpx.HTTPError:
                    pass
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise AssertionError("Actual notification renderer host failed to start: " + log_path.read_text()[-2000:])
                time.sleep(0.1)
            yield
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if thread.is_alive():
            server.shutdown()
            thread.join(timeout=5)
        server.server_close()
        subprocess.run([sys.executable, "-c", seed, actor, plugin, installation, "yes"],
                       env=env, check=True, capture_output=True, text=True)
        supervisor.gateway_url, supervisor.gateway_token, supervisor.gateway_configuration_source = old_gateway
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value