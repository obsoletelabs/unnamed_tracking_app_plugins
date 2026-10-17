"""Command-line acceptance flow: discover, request, wait for consent, read, rotate."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .client import READ_SCOPES, WRITE_SCOPES, AccessDenied, ReferenceClient
from .store import CredentialStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="utp-integration-client")
    parser.add_argument("--instance", required=True, help="HTTPS URL of the tracking instance")
    parser.add_argument("--name", default="Reference client")
    parser.add_argument("--origin", required=True, help="This client's exact HTTPS origin")
    parser.add_argument("--store", type=Path, default=Path.home() / ".utp-integration.json")
    parser.add_argument("--allow-insecure-localhost", action="store_true")
    parser.add_argument("--read", nargs="*", default=["profile.read", "games.read"])
    parser.add_argument(
        "--write", nargs="*", default=[], help="Optional writes; asked for only when listed"
    )
    parser.add_argument("--rotate", action="store_true")
    args = parser.parse_args(argv)
    bad = (set(args.read) - READ_SCOPES) | (set(args.write) - WRITE_SCOPES)
    if bad:
        parser.error(f"unsupported capabilities: {sorted(bad)}")

    client = ReferenceClient(
        args.instance,
        name=args.name,
        origin=args.origin,
        allow_insecure_localhost=args.allow_insecure_localhost,
    )
    info = client.discover()
    print(f"Target instance: {info.instance_id} ({info.base_url})")
    store = CredentialStore(args.store)
    saved = store.load(info.instance_id)
    session = None
    if saved:
        try:
            session = client.session_from_token(saved["token"], info.instance_id, saved["grant_id"])
        except Exception:  # expired, revoked or disabled: start a fresh consent flow
            store.forget(info.instance_id)
    if session is None:
        pending = client.request_access(args.read + args.write)
        print(f"I am '{args.name}' ({args.origin}) requesting: {', '.join(pending.scopes)}")
        print(f"Open and review in your browser: {pending.verification_url}")
        while session is None and time.time() < pending.expires_at:
            time.sleep(pending.poll_interval)
            try:
                session = client.exchange(pending)
            except AccessDenied:
                print("Access was denied.")
                return 1
        if session is None:
            print("The request expired.")
            return 1
        store.save(info.instance_id, session.token, session.grant_id)
    if args.rotate:
        session.rotate()
        store.save(info.instance_id, session.token, session.grant_id)
    expiry = "until revoked" if session.ongoing else f"until {session.expires_at}"
    print(f"Granted: {', '.join(session.scopes)} ({expiry})")
    if session.has("profile.read"):
        print("Profile:", session.profile())
    if session.has("games.read"):
        print("Games page:", session.games(limit=5))
    return 0


if __name__ == "__main__":
    sys.exit(main())
