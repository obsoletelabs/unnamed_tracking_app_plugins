"""Validate maintained source contracts before generating any packages."""
from __future__ import annotations

try:
    from .distribution import ROOT, canonical_json, collect_payload, discover_plugins
    from .validate_packages import validate_current_contract
except ImportError:
    from distribution import ROOT, canonical_json, collect_payload, discover_plugins
    from validate_packages import validate_current_contract


def check(root=ROOT) -> None:
    plugins = discover_plugins(root)
    for source, manifest in plugins:
        if manifest.get("api_contract_version") not in {"1.1.0", "1.1.1", "1.1.2", "1.1.3"}:
            raise ValueError(f"{source.name}: maintained source must explicitly target Plugin API v1.1.0, v1.1.1, v1.1.2 or v1.1.3")
        files, metadata = collect_payload(root, source, manifest)
        # The existing validator expects generated version/policy fields.
        # Resolve them only for this static validation; write no artifacts.
        files["distribution.json"] = canonical_json({
            **metadata, "version": manifest["version"],
            "automatic_update": metadata["automatic_update"] is not False,
        })
        validate_current_contract(manifest, files)
    print(f"Validated {len(plugins)} maintained plugin source contracts")


if __name__ == "__main__":
    check()
