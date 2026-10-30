# Exposed test signing key (`non-secret-testkey`)

`non-secret-testkey` is a **test** Ed25519 identity whose private seed was exposed in
Git history. Treat the seed as public: anyone can sign with it.

## Current state

| Property | Value |
| --- | --- |
| Registry status | `retiring` (matches the host registry) |
| Scope | `example.` only, channel `demo` |
| New release signing | Refused: `release_signer` and `--require-signing` accept only `active` keys |
| Existing packages | 33 immutable historical `.utp` files in `dist/` remain verifiable |

The key was once removed from the registry (`a49e34f`) and later re-added as `active`
(`88593ed`). It is now `retiring` and a regression test fails if it returns to `active`.

## Historical exposure

Every package in `dist/` signed by this key (including the former `example.*`
catalogue versions) must be regarded as signed with a compromised key. Their payload
digests are unchanged and the files are immutable, but the signature proves nothing
about who built them. The test suite freezes the exact set of filenames signed by the
key, so a forged package signed with the leaked seed cannot be added to `dist/`
unnoticed.

## Why `retiring` rather than `revoked`

Revoking the key makes verification of those historical artifacts fail, including
the previously published catalogue versions of the maintained plugins, and they cannot
be re-signed without the examples private key. Re-signing the affected current
versions with `unnamed-tracking-examples-2026-10-v1` and then marking the key
`revoked` is the recommended follow-up (it needs a maintainer holding that secret).
After that, `revoked` keys are rejected by `PublisherRecord.allows_plugin` for both
verification and release.

## Replacement guidance

* Sign `example.*` packages with `unnamed-tracking-examples-2026-10-v1`
  (`PLUGIN_EXAMPLES_SIGNING_KEY_ID` / `PLUGIN_EXAMPLES_SIGNING_KEY_B64`).
* Sign `official.*` packages only with `unnamed-tracking-official-2026-10-v1`.
* Never commit a private seed, including one labelled non-secret or temporary.
* Do not re-register a retired or revoked key as `active`; register a new identity
  in `publishers/registry.json` and the host registry together.
