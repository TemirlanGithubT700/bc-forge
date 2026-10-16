# Offline payment-export reconciliation: a practical QA checklist

> **Scope:** General-purpose payment export QA, useful when reviewing reports derived from wallet transfers, batch payouts, gateways, or event indexers. This note does **not** claim that the `bc-forge` contracts, the linked demonstration, or the sold Python tool independently verify on-chain settlement. This is a separate educational resource, not an integration or a change to this repository's smart contracts.

## Why a raw CSV sum is not a reliable settlement total

A payment export can contain:
- Duplicate records for the same payment ID after retrying a poll or ingestion job.
- Conflicting values for a reused payment ID.
- Pending rows that should not yet be counted as settled.
- Inbound and outbound flows in different assets or networks.
- Fractional monetary amounts that binary floating-point arithmetic can round.

If a dashboard simply sums the `amount` column, it can produce a misleading apparent balance. The status and provenance of every record matter.

## Minimal synthetic fixture

```csv
payment_id,network,asset,status,direction,amount
pay-101,Base,USDC,settled,incoming,12.50
pay-102,Base,USDC,settled,outgoing,2.25
pay-103,Base,USDC,pending,incoming,8.00
pay-104,Base,USDC,settled,incoming,0.75
pay-104,Base,USDC,settled,incoming,0.75
pay-105,Base,USDC,settled,incoming,3.00
pay-105,Base,USDC,settled,incoming,4.00
pay-106,Arbitrum,USDC,settled,outgoing,1.00
pay-107,Base,USDT,settled,incoming,1.1234567
pay-108,Base,USDC,settled,incoming,8.00
```

This sample is illustrative, not chain data.

Key observations:
1. `pay-104` is repeated with identical fields. Count it once, with a duplicate notice.
2. `pay-105` reuses the same ID with different amounts. Flag and exclude it until reviewed.
3. `pay-103` is pending. It must not inflate settled net balances.
4. `pay-107` contains seven fractional digits; reject it for a chosen six-decimal USDC-like amount constraint. A real system should use the asset's own verified precision.
5. Separate network and asset dimensions: a Base/USDC figure cannot be combined blindly with Arbitrum/USDC or Base/USDT.

For this fixture, **Base / USDC settled net = 19.00 units**, because 12.50 - 2.25 + 0.75 + 8.00 = 19.00. This is a *local data-quality result*, not proof of chain finality, transaction validity, or merchant payout.

## Minimum validation workflow

1. **Preserve the original export.** Keep source, timestamp and schema metadata outside the reconciled table.
2. **Validate the schema and amount precision.** Reject invalid numeric representations and missing IDs rather than silently coercing them.
3. **Classify duplicate vs. conflicting IDs.** Identical retries should not double-count; different payloads require review.
4. **Distinguish observed vs. settled status.** A service-provided status field remains a claim from that service until separately verified if chain finality matters.
5. **Group by asset and network.** Compute `incoming - outgoing` per group using decimal or scaled-integer math.
6. **Produce audit-friendly exceptions.** Report the offending ID, issue type, and affected row(s).
7. **Reconcile against authoritative upstream systems separately.** A CSV processor alone cannot detect missing events, chain reorgs, bogus settlement labels or compromised exports.

## Free interactive example

**Long-lived downloadable version:** [payment-export-reconciliation-demo.html](payment-export-reconciliation-demo.html) — use GitHub's **Download raw file** action, then open the saved HTML locally in your browser. This does not depend on PageShare hosting and requires no installation. It is a separate, limited educational demonstration, not the sold Python CLI.

I have also published a **free synthetic CSV demo** of these general QA ideas:

**[Try the browser-based reconciliation example](https://bright-tide-5545.hosted.pageshare.ai)**

It processes entered records locally and exports a JSON report. The current free public hosting expires **22 October 2026**, so that hosted URL may stop working after that date. The page is illustrative, not a reproduction of the paid tool.

## Optional fuller Python CLI

Disclosure: **The person publishing this educational resource is also the owner/seller of the linked commercial toolkit.** The link below is promotional and entirely optional; the checklist and synthetic example above are free to use.

**[Revenue Ledger QA Kit — offline payment reconciliation](https://speedbot.dev/products/product_b469bc0491a04855bce0e75da7904113)** is listed for **1.99 USDC** (check the live listing for current terms). The advertised bundle includes Python 3 source code, CSV/JSON/JSONL handling, exact Decimal processing, duplicate/conflict and pending/settled diagnostics, 17 regression tests, a README, sample files and a commercial-use license.

**Limitations:** It is not a blockchain explorer, a chain finality oracle, a protocol fix, or a drop-in adapter for arbitrary x402 facilitator JSON. It analyzes correctly structured records supplied to it. No claims about sales or buyer endorsements are made.

Feedback about useful export schemas and reconciliation edge cases is welcome; no purchase is required to discuss the technique.
