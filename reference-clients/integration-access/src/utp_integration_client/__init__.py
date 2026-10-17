"""Platform-neutral reference consumer of the public delegation v1 contract.

Uses only the Python standard library and the documented HTTP paths below
``/api/delegation/v1``. It imports nothing from the host or from any identity
provider adapter.
"""

from .client import (
    READ_SCOPES,
    WRITE_SCOPES,
    AccessDenied,
    ConsentRequest,
    GrantSession,
    InstanceInfo,
    IntegrationError,
    MissingCapability,
    ReferenceClient,
)
from .store import CredentialStore

__all__ = [
    "READ_SCOPES",
    "WRITE_SCOPES",
    "AccessDenied",
    "ConsentRequest",
    "CredentialStore",
    "GrantSession",
    "InstanceInfo",
    "IntegrationError",
    "MissingCapability",
    "ReferenceClient",
]
