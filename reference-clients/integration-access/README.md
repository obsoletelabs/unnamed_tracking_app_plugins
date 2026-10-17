# Integration access reference client

A small, standard-library-only Python consumer of the host's public **scoped
integration access** contract (`/api/delegation/v1`, protocol 1.0). It is
platform-neutral: it identifies itself by a name and exact HTTPS origin, never by
a Discord (or any other) identity, and imports nothing from the host or from this
repository's plugin SDK. Identity providers stay in their own adapters; if your
integration has a linked external account, pass it as display context only
(`external_account`), which the consent screen and **Account → Connected apps**
show but which never proves ownership.

This is not a plugin and has no `.utp` package. It is an independently hosted
client, distributed as a Python package (`pip install ./reference-clients/integration-access`,
console script `utp-integration-client`).

## What it demonstrates

| Contract behavior | Client API |
| --- | --- |
| Discover target instance, policy and approved clients | `ReferenceClient.discover()` |
| Origin approval, or registration under the optional "any HTTPS origin" policy (no data access) | `client_id()` |
| Request exactly the capabilities you list; read-only by default | `request_access(scopes)` |
| Verifier-bound, one-use exchange; denial and pending states | `exchange(pending)` |
| Timed and **Until revoked** grants (`expires_at: null`) | `GrantSession.ongoing` |
| Optional writes need their own explicit consent and are blocked client-side without it | `GrantSession.update_tracking()` |
| Credential rotation without more access or a longer expiry | `GrantSession.rotate()` |
| Reduction/revocation by the user, disabled clients, owner policy | surfaced as `IntegrationError` (401/403) |
| Credential kept out of URLs and logs; owner-only file | `CredentialStore` |

Legacy `utk_` API keys are a separate mechanism, not accepted here, and keep
working unchanged on the ordinary API.

## Use

```python
from utp_integration_client import ReferenceClient

client = ReferenceClient("https://tracker.example.com", name="My notes app",
                         origin="https://notes.example.com")
info = client.discover()                      # show info.instance_id to your user
pending = client.request_access(["profile.read", "games.read"])
print("Approve in your browser:", pending.verification_url)
# poll no faster than pending.poll_interval until exchange() returns a session
session = client.exchange(pending)
print(session.profile(), session.games())
```

Command line: `utp-integration-client --instance https://tracker.example.com --origin
https://notes.example.com [--write tracking.write]`. Use
`--allow-insecure-localhost` only for a local test instance.

## Tests

```bash
python -m pytest tests/test_integration_reference_client.py
python tools/check_integration_access.py --instance http://127.0.0.1:8000 \
  --allow-insecure-localhost --admin admin:pw --user-a alice:pw --user-b bob:pw
```

The first runs against an in-memory contract double and needs no host. The second
is an explicit live acceptance run against a disposable installation (it changes
integration policy and creates test games).
