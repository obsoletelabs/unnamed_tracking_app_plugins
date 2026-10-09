# Audit release history before publication

Every current and historical release record is checked against the actual
immutable archive, including retired plugins' retained packages:

```sh
python tools/distribution.py
python tools/distribution.py --baseline-ref origin/main
python tools/build_packages.py
python tools/distribution.py --root .validation --check-source --include-unreleased
```

The first check reconstructs metadata from each `.utp`, verifies payload integrity,
signature and scoped publisher, and compares the package with its record. The
second compares baseline package bytes and append-only record prefixes, and
rejects disappearance of a baseline plugin from the generated current catalogue.
The preview check also binds each latest record to the current source digest.

Retirement is an explicit reviewed decision in the repository-root
`retired_plugins.json`. Each record names a plugin ID, has `status: retired` and
explains the reason. Advanced, Events, Lifecycle and the legacy Discord Delivery
Provider are retired. Discord Notifications uses a new official identity and
protected host-owned endpoints; old credentials and consent are never transferred. A retired ID must have no
maintained source or current catalogue entry, and must retain its release history.
The baseline check still requires every historical archive byte and release
record prefix to remain unchanged. Retirement does not uninstall an existing
plugin or erase its published package URLs.

| Field | Authoritative evidence |
| --- | --- |
| `package_sha256`, size and filename | Exact final archive bytes and plugin ID/version |
| `sha256` | Canonical v1 payload digest, verified independently |
| Manifest and version | Actual `manifest.json` in the archive |
| Signing and publisher | Manifest integrity plus reviewed public-key registry/scope/status |
| README | Packaged `payload/README.md` text |
| Tags, release notes and automatic-update policy | Packaged `distribution.json` release snapshot |
| Build provenance | Packaged metadata for current-format releases |
| Catalogue latest entry and history | Authoritative release records and hosting configuration |

Legacy releases may predate embedded README/distribution policy. Their records
preserve that absence and require manual update approval; do not invent a modern
README or automatic consent for an old package.

If a record disagrees with a package, stop publication and identify the source of
the mismatch. Preserve the original archive/record for review. Fix authoring or
the generation bug in a new release; do not silently edit an old manifest, notes,
policy, signature, publisher identity or ZIP. A baseline catalogue removal fails
deliberately even when retained histories remain valid; retirement requires an
explicitly reviewed policy change.

CI rejects unindexed `.utp` output, incorrect metadata/hashes, changed historical
bytes, broken documentation references and missing catalogue identities. The
normal unsigned developer build stays under `.validation/`. Signed publication
and GitHub release uploads keep the existing [publishing workflow](packages.md).
