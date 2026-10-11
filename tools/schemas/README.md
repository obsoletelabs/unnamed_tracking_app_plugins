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

Lifecycle query/page snapshots describe the additive public API 1.1.4 extension. Older notification schemas retain their 1.1.2 identities. The explicit read grant is standalone and not implied by sending/provider permissions.

The provider schema and capability enum include the additive API1.1.6 possession-proof extension. PRIVATE kinds declare verification/sensitive/recovery features, never SECURE trust. Host challenge proof and an independent critical notification_providers.sensitive grant govern handoff. Existing content/destination DTOs retain their API1.1.5 shape.


API1.1.7 adds the independent critical auth.password_reset permission and auth-password-reset-v1 contribution schema, exported by host tools/export_auth_contract.py. The provider/content schemas retain their previous versions. Paired host checks validate this schema and actual packaged consumers.


API 1.1.8 adds the independent critical auth.user_invites grant and three bounded invitation contribution/input schemas. The reset schema remains 1.1.7; earlier provider schemas retain their established versions. Paired checks compare exact host exports and actual packaged consumers.
