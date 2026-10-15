# HowLongToBeat Metadata Provider

The updated source requires public Plugin API **1.1.13** and the host completion-estimates
update in [host PR #136](https://github.com/obsoletelabs/unnamed_tracking_app_2/pull/136).
It uses no account or API key. Install the corresponding published `.utp` through
Plugin Manager and grant its declared metadata, network and storage permissions.

The provider initializes a short-lived public search token, then searches the
site's current endpoint with browser headers. A search 403 renews the token and
retries once; a second rejection stops. Tokens are not persisted or logged. The
SDK returns 403 directly to the provider instead of multiplying that renewal with
generic background retries. Other failures retain bounded SDK pacing/retry policy.

Metadata returns whichever of Main story, Main + extras, Completionist and All
play styles are available, normalized to one-decimal hours. Missing or invalid
figures are omitted, including when Main story is absent. Existing HLTB identity
wins; without one, only a unique exact normalized title is accepted. Community
estimates never write personal playtime. The host applies manual field protection,
account/provider choices and per-category native IGDB fallback independently.

Build development packages with `python tools/build_packages.py`. Unsigned previews require explicit installation consent; the existing release workflow produces signed publication packages.

Run `python -m pytest tests/test_hltb.py tests/test_metadata_providers.py -q`.
Fixtures cover token renewal bounds, partial/invalid figures, selected identity,
ambiguity and the exported wire schema. A direct public token/search check on
15 October 2026 returned five Portal results; this does not establish installed
package success. Package/runtime integration validation is tracked in the PR.
