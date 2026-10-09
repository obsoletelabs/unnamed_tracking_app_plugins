# Build and publish packages

Author runtime declarations in `manifest.json`, behavior/assets in the source
directory, and distribution inputs in `release.json`:

```json
{"schema_version": 1, "publisher": "Example Community", "tags": ["games", "statistics"], "icon": null, "automatic_update": null, "release_notes": "Adds the library summary action."}
```

The builder puts a generated `distribution.json` snapshot in the signed payload.
README, icon, tags, notes and resolved update policy stay attached to that release.
Never put plugin-authored risk fields in either manifest or release metadata.

## Validate a preview

```sh
python tools/check_source_layout.py
python -m pytest
python tools/build_packages.py
python tools/distribution.py --root .validation --check-source --include-unreleased
python tools/verify_packages.py .validation/dist/*.utp
python tools/validate_packages.py .validation/dist/*.utp
python -m mkdocs build --strict
```

On PowerShell, native-command wildcards are not expanded: pipe paths using
`Get-ChildItem .validation/dist/*.utp | ForEach-Object { python tools/verify_packages.py $_.FullName; python tools/validate_packages.py $_.FullName }`.
The preview never updates official artifacts or source versions. New packages
are unsigned unless a legitimate registered signer is supplied. Unchanged
historical packages are copied byte for byte.

## Publish the authoritative snapshot

Commit authoring/tooling/publisher changes first. Supply `PLUGIN_SIGNING_KEY_B64`
and `PLUGIN_SIGNING_KEY_ID` through secure CI secrets and use the existing
`python tools/build_packages.py --require-signing` command. It verifies the
signer, generates deterministic archives, calculates payload and complete package
hashes, verifies signatures/contracts and writes `dist/`, `releases/`, `list.json`
and resolved source versions together.

Verify `python tools/distribution.py --check-source` and immutable history against
the previous published Git revision. The official serialized publication workflow
is the only official release path. Missing keys fail; no unsigned fallback exists.
Tag a generated main snapshot only after publication succeeds. GitHub release
events require already-published source and upload the same package/list/history
assets. They do not replace append-only repository release records.

## Promote a tested source preview

Sources in `catalogue.json.unreleased_plugins` are validated and packaged by
development checks but intentionally excluded from routine signed publication.
After review, use **Publish plugin packages** → **Run workflow** on `main` and
enter the exact approved IDs in `promote_plugins`, separated by spaces. For the
notification routing demonstrations these IDs are
`example.password-reset-notification-demo` and
`example.user-invite-notification-demo`.

The existing serialized publisher reruns all checks, signs with the registered
folder-specific key, validates the complete distribution, then commits archives,
release histories, catalogue entries and removal of those preview markers in the
same publication commit. A failed signature, invalid package or unknown ID leaves
preview policy and published artifacts unchanged. Other preview IDs stay excluded;
the demo signing channel does not make these production authentication features.

Independent catalogue owners can use the same builder:

```bash
python tools/build_packages.py --publish --promote-plugin example.my-tested-plugin
```

Repeat `--promote-plugin` for multiple IDs. Promotion requires committed source,
an existing explicit preview entry and the appropriate registered signer. It is
unavailable for unsigned development builds, catalogue-only indexing or tagged
release reuse. Never remove the preview entry before its first signed publication.
