"""Small helpers around the OAuth token; no Home Assistant imports so they stay unit-testable."""

from __future__ import annotations

import base64
import json
from typing import Any


def jwt_claims(token: str | None) -> dict[str, Any]:
    """Return the payload of a JWT without verifying it.

    Verification is Keycloak's and the API's job; here the claims only name the
    account (unique id, title). Anything malformed yields an empty dict.
    """
    if not token or token.count(".") != 2:
        return {}
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
    except (ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def account_identity(token_data: dict[str, Any]) -> tuple[str | None, str]:
    """(unique id, display title) for the account behind an OAuth token response."""
    claims = jwt_claims(token_data.get("id_token")) or jwt_claims(token_data.get("access_token"))
    unique_id = claims.get("sub")
    title = claims.get("email") or claims.get("preferred_username") or claims.get("name") or "BAPP Auto"
    return (str(unique_id) if unique_id else None, str(title))
