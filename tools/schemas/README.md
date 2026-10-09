# Plugin API v1 public schemas

These JSON Schemas were exported with Pydantic `model_json_schema()` from
`PluginManifest` and `PluginUiDocument` on the host's `feat/metadata-provider-orchestration`
branch for the additive v1.1.1 contract. The wire major remains `v1`. New metadata
providers declare `api_contract_version: "1.1.1"`; existing v1.1.0 plugins remain supported.
An absent declaration remains v1.0.0 and cannot execute on the new host.

They are validation contracts, not a second runtime or SDK. The local validator
also checks semantic versions, declaration uniqueness, executable handlers,
references and packaged release metadata. `tools/check_host_contract.py` checks
new packages against the actual host models and installation registry. When the
public contract changes, review and re-export both schemas, and run that check.
# Metadata provider extension

The metadata registration/request/response snapshots describe Plugin API 1.1.1.
They are exported by the companion host's `tools/export_metadata_contract.py`.
Provider plugins use these public schemas without importing host internals.

Notification source/event/provider/layout schemas describe the public API 1.1.2 extension and are exported by the host tools/export_notification_contract.py. Both schemas and packaged consumers are checked by check_host_contract.py against the paired host.
