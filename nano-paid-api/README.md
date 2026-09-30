# Global Weather & FX API — independent Nano pay-per-call component

Public, non-secret source mirror of the Nano seller's payment verification and anti-replay implementation. This is a **separate Nano demonstration branch**, not part of bc-forge's Stellar/Soroban contracts. Code was prepared and unit/integration tested on **2026-09-30**. **Do not interpret this branch as proof that the anti-replay release has reached production**: production release and environment verification must be separately checked.

## Actual Nano seller

- Stable seller origin: `https://built-with-productos-xszv.vercel.app`
- API: `GET /nano/v1/hash?text=hello`
- Price: `0.001 XNO` per *single* call
- Current public pay-to: `nano_1bpdjdo1c14uhh7yzq9wa5diwkxtoi9madniqtrg8pf353yg6hs8fkwmz4bs`
- No signup or API key. An unpaid request normally returns an HTTP 402 challenge showing the amount and address. A paid request carries the confirmed **Nano send block hash** in `X-Nano-Payment`.
- `app.py` performs independent confirmation / subtype / recipient / amount verification using Nano RPC. `nano_claims.py` then atomically consumes that verified send hash using private S3 conditional `PUT` (`If-None-Match: *`). It refuses retries with an already-consumed hash and fails closed if storage is absent. Credentials are environment-only; none are published here.

## Historical external payments, independently checkable on Nano mainnet

The public Nano chain confirms the transfer facts. Buyer attribution as Pursekeeper comes from the agent's seller emails and own public log, not from the blockchain alone.

| Role | Nano send block | Seller receive block | Amount | Classification |
| --- | --- | --- | --- | --- |
| First paid API call to original seller address | `0E4C6AF53B9F8F989FBAD2922FF42DB5CBC8D46EB41B24545B9C9F9C613D992D` | `84C4B06A700CD9C1CD4D9211DE7434E26E559CAE4327D9654D3E4BFF0A3B8BC4` | 0.001 XNO | Sale |
| Second paid call to new seller address | `5EC854A66DDECD57DA7143FF0EC742E972FC0A80C4FC26D6E3B2CD12B23D3D97` | `7F44D8A2507EEC44168CA7542BE24EED7D6A49168A42B408E82624605869F217` | 0.001 XNO | Sale |
| Separate newcomer credit | `5062B6F09B8E36F8D6C753D1344E26FB8DDC7AD32EF07BEAF2B6654C85036812` | `D37802541DED15CA1335396B96095838697EB786C1FB632C94144ED3E0865C17` | 10 XNO | **Bonus, NOT a sale** |

To verify, query a trusted Nano mainnet node's `block_info` method with each hash; the corresponding receive block's `contents.link` contains the source send block, and each confirmed amount must match. Both paid API calls were also acknowledged by the independent agent in its emails. The second paid send hash was pre-marked as consumed in the project's private S3 ledger before deployment of anti-replay code. This historical Nano evidence **does not constitute Base USDC x402 or Tempo MPP settlement** and must not be counted as x402 marketplace purchase history.

## Deployment safety

The separate production app imports these handlers into its own `main.py` and also serves x402 / MPP routes. The pre-deployment tests covered concurrent duplicate claims, missing storage, backend failure, and an already-used genuine Nano hash. A successful code test is not a substitute for a **live** production 402 replay check. Do not send new Nano payments when `/nano/v1/hash` reports `503 nano_payments_temporarily_unavailable`.
