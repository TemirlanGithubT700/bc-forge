"""Durable, atomic, single-use Nano payments backed by private project S3.

S3 conditional PutObject (If-None-Match: *) atomically claims a Nano send hash
across serverless instances; missing credentials or storage failure fail closed.
No keys or credentials belong in this source file.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

import httpx


class NanoClaimAlreadyUsed(Exception):
    """A confirmed Nano send was consumed by an earlier paid API invocation."""


class NanoClaimUnavailable(Exception):
    """Cannot safely account for a payment; refuse the paid response."""


def nano_storage_configured() -> bool:
    """Secret configuration readiness, NOT a guarantee that S3 is online."""
    return (os.environ.get("PRODUCTOS_STORAGE_ENDPOINT", "").strip().startswith("https://")
            and bool(os.environ.get("PRODUCTOS_STORAGE_TOKEN", "").strip())
            and bool(os.environ.get("PRODUCTOS_STORAGE_PROJECT_ID", "").strip()))


async def claim_nano_send_once(block_hash: str, amount_raw: str, request_text: str) -> None:
    """Atomically consume a fully RPC-verified send block hash exactly once.

    Caller MUST verify Nano send block hash, recipient, confirmation and amount
    through a trusted Nano node first. This module enforces uniqueness only.
    On storage failure it fails CLOSED: never return paid API data.
    """
    gateway = os.environ.get("PRODUCTOS_STORAGE_ENDPOINT", "").strip()
    token = os.environ.get("PRODUCTOS_STORAGE_TOKEN", "").strip()
    project_id = os.environ.get("PRODUCTOS_STORAGE_PROJECT_ID", "").strip()
    if not (gateway.startswith("https://") and token and project_id):
        raise NanoClaimUnavailable("Project S3 storage is not configured")
    if len(block_hash) != 64 or any(ch not in "0123456789ABCDEF" for ch in block_hash):
        raise ValueError("Unvalidated Nano payment hash")

    object_path = f"nano-claims/v1/{block_hash}.json"
    payload = json.dumps({
        "version": 1,
        "hash": block_hash,
        "amount_raw": amount_raw,
        "request_sha256": hashlib.sha256(request_text.encode("utf-8")).hexdigest(),
        "claimed_at": datetime.now(timezone.utc).isoformat(),
    }, separators=(",", ":")).encode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
            gateway_result = await client.post(
                gateway,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "op": "put",
                    "projectId": project_id,
                    "path": object_path,
                    "contentType": "application/json",
                    "visibility": "private",
                },
            )
            gateway_result.raise_for_status()
            signed_upload = gateway_result.json().get("url", "")
            if not signed_upload.startswith("https://"):
                raise NanoClaimUnavailable("Storage gateway did not return a secure upload URL")
            claim = await client.put(
                signed_upload,
                content=payload,
                headers={"Content-Type": "application/json", "If-None-Match": "*"},
            )
            if claim.status_code in (409, 412):
                raise NanoClaimAlreadyUsed()
            claim.raise_for_status()
            if claim.status_code not in (200, 201, 204):
                raise NanoClaimUnavailable(f"Unexpected S3 claim status {claim.status_code}")
    except (NanoClaimAlreadyUsed, NanoClaimUnavailable):
        raise
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise NanoClaimUnavailable("Durable payment ledger request failed") from exc
