// Public reference implementation for the Nano payment gate used by
// https://agent-chain-kit-solana.vercel.app/nano/v1/hash
//
// Protocol:
//   - unpaid GET => HTTP 402, nano:mainnet, price + pay_to
//   - client pays the Nano address and sends the confirmed send block hash in
//     X-Nano-Payment
//   - a confirmed payment hash is single-use; a replay is rejected
//
// This file intentionally contains no wallet seed/private key. Verification only
// needs public Nano-chain data plus durable replay state.

import crypto from 'node:crypto';

export const NETWORK = 'nano:mainnet';
export const ASSET = 'XNO';
export const PRICE = '0.001 XNO';
export const PRICE_RAW = '1000000000000000000000000000';
export const PAY_TO = 'nano_1bpdjdo1c14uhh7yzq9wa5diwkxtoi9madniqtrg8pf353yg6hs8fkwmz4bs';
export const PAYMENT_HEADER = 'X-Nano-Payment';

function paymentRequired(extra = {}) {
  return Response.json({
    error: 'payment_required',
    scheme: 'nano-block-hash',
    network: NETWORK,
    asset: ASSET,
    price: PRICE,
    price_raw: PRICE_RAW,
    pay_to: PAY_TO,
    payment_header: `${PAYMENT_HEADER}: <confirmed send block hash>`,
    ...extra,
  }, {
    status: 402,
    headers: {
      'Cache-Control': 'no-store',
      'X-Payment-Network': NETWORK,
      'X-Payment-Address': PAY_TO,
      'X-Payment-Amount-Raw': PRICE_RAW,
    },
  });
}

/**
 * Production integration contract.
 *
 * verifyConfirmedNanoSend(blockHash) must use public Nano chain data and return
 * true only when blockHash is a confirmed SEND paying at least PRICE_RAW to
 * PAY_TO.
 *
 * usedPayments must be durable/atomic storage. `claim(hash)` must return false
 * when the hash was already consumed, and true only once for a new hash.
 */
export async function handleNanoHashRequest(request, {
  verifyConfirmedNanoSend,
  usedPayments,
}) {
  const url = new URL(request.url);
  const text = url.searchParams.get('text') ?? '';
  const paymentHash = request.headers.get(PAYMENT_HEADER);

  if (!paymentHash) return paymentRequired();

  if (!/^[A-Fa-f0-9]{64}$/.test(paymentHash)) {
    return paymentRequired({ error: 'invalid_nano_payment_hash' });
  }

  const valid = await verifyConfirmedNanoSend(paymentHash, {
    network: NETWORK,
    payTo: PAY_TO,
    minimumRaw: BigInt(PRICE_RAW),
  });

  if (!valid) {
    return paymentRequired({ error: 'nano_payment_not_confirmed' });
  }

  // IMPORTANT: this must be an atomic first-writer-wins operation. Checking and
  // then writing in two separate non-atomic calls would re-introduce replay races.
  const firstUse = await usedPayments.claim(paymentHash.toUpperCase());
  if (!firstUse) {
    return paymentRequired({
      error: 'nano_payment_already_used',
      detail: 'This Nano send hash already paid for one call. Send a fresh payment for another call.',
    });
  }

  return Response.json({
    sha256: crypto.createHash('sha256').update(text).digest('hex'),
    confirmed: true,
  }, {
    status: 200,
    headers: { 'Cache-Control': 'no-store' },
  });
}
