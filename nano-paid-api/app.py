"""Public mirror of the Global Weather & FX API's standalone Nano paid route.

This example is separate from bc-forge's Soroban contracts and requires
privately configured ProductOS storage credentials. NEVER commit .env/seed.
Production currently uses the Nano handlers inside its larger main.py.
"""
from __future__ import annotations

import hashlib
import json

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from nano_claims import (
    NanoClaimAlreadyUsed,
    NanoClaimUnavailable,
    claim_nano_send_once,
    nano_storage_configured,
)

app = FastAPI(title="Global Weather & FX API - Nano payment verifier")
NANO_PRICE_RAW = "1000000000000000000000000000"  # 0.001 XNO
NANO_PAY_TO = "nano_1bpdjdo1c14uhh7yzq9wa5diwkxtoi9madniqtrg8pf353yg6hs8fkwmz4bs"
NANO_RPC_URL = "https://rpc.nano.to"


def payment_required(error: str = "payment_required") -> JSONResponse:
    return JSONResponse(
        status_code=402,
        headers={
            "X-Payment-Address": NANO_PAY_TO,
            "X-Payment-Amount-Raw": NANO_PRICE_RAW,
            "X-Payment-Network": "nano:mainnet",
            "Cache-Control": "no-store",
        },
        content={
            "error": error,
            "scheme": "nano-block-hash",
            "network": "nano:mainnet",
            "asset": "XNO",
            "price": "0.001 XNO",
            "price_raw": NANO_PRICE_RAW,
            "pay_to": NANO_PAY_TO,
            "payment_header": "X-Nano-Payment",
            "instructions": "Send 0.001 XNO to pay_to, then send a single request with the confirmed send block hash in X-Nano-Payment. A hash can pay for exactly one call.",
        },
    )


async def verify_nano_send(block_hash: str) -> dict:
    block_hash = block_hash.strip().upper()
    if len(block_hash) != 64 or any(ch not in "0123456789ABCDEF" for ch in block_hash):
        raise HTTPException(402, "X-Nano-Payment must be a 64-character Nano block hash")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                NANO_RPC_URL,
                json={"action": "block_info", "json_block": "true", "hash": block_hash},
            )
            response.raise_for_status()
            info = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Nano payment verification unavailable") from exc

    if info.get("error"):
        raise HTTPException(402, "Nano send block not found")
    if str(info.get("confirmed", "")).lower() != "true":
        raise HTTPException(402, "Nano send not confirmed")
    if info.get("subtype") != "send":
        raise HTTPException(402, "Nano block is not a send payment")
    if info.get("contents", {}).get("link_as_account") != NANO_PAY_TO:
        raise HTTPException(402, "Payment destination does not match")
    try:
        amount_raw = int(info.get("amount", "0"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(402, "Invalid Nano payment amount") from exc
    if amount_raw < int(NANO_PRICE_RAW):
        raise HTTPException(402, "Insufficient Nano payment amount")
    return {"hash": block_hash, "amount_raw": str(amount_raw), "confirmed": True}


@app.get("/nano/v1/hash")
async def nano_hash(request: Request, text: str = Query(..., min_length=1, max_length=10_000)):
    # Avoid asking buyers to pay when this instance cannot account for payments.
    if not nano_storage_configured():
        return JSONResponse(
            status_code=503,
            content={"error": "nano_payments_temporarily_unavailable",
                     "detail": "Single-use payment ledger is not configured. Do not pay yet."},
            headers={"Retry-After": "60", "Cache-Control": "no-store"},
        )
    block_hash = request.headers.get("X-Nano-Payment", "").strip()
    if not block_hash:
        return payment_required()
    payment = await verify_nano_send(block_hash)
    try:
        await claim_nano_send_once(payment["hash"], payment["amount_raw"], text)
    except NanoClaimAlreadyUsed:
        return payment_required("nano_payment_already_used")
    except NanoClaimUnavailable:
        raise HTTPException(503, "Durable ledger unavailable. Contact seller before paying again.",
                            headers={"Retry-After": "30"})
    return {"text": text, "algorithm": "sha256", "hex": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "payment": payment, "seller": "Global Weather & FX API"}


@app.get("/nano")
async def nano_docs():
    return {"endpoint": "/nano/v1/hash?text=hello", "network": "nano:mainnet",
            "price": "0.001 XNO", "pay_to": NANO_PAY_TO,
            "ledger_secrets_configured": bool(nano_storage_configured())}
