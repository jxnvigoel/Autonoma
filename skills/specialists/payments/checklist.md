# Specialist Pack: Payments & Idempotency Checklist

Review this checklist before submitting any payment-related story or endpoint.

- [ ] **Idempotency Header Enforced**: `Idempotency-Key` is required on all financial POST endpoints; missing key returns HTTP 400.
- [ ] **Cached Response on Duplicate**: Identical idempotency key with status `COMPLETED` returns cached response without duplicate billing.
- [ ] **In-Progress Concurrency Protected**: In-progress duplicate requests return HTTP 409 Conflict with `Retry-After`.
- [ ] **Zero Card Data Stored**: No raw PAN (16 digits) or CVV/CVC stored in database or printed in logs.
- [ ] **Tokenized Storage**: Only gateway payment method tokens, brand, and last 4 digits stored.
- [ ] **Webhook Signature Verified**: Webhook endpoint calculates HMAC-SHA256 over raw request bytes and compares with signing secret using constant-time comparison.
- [ ] **Replay Protection**: Webhook timestamp drift verified to be ≤ 300 seconds.
- [ ] **Webhook Deduplication**: Webhook `event_id` recorded in `processed_webhooks` to prevent duplicate processing.
- [ ] **Failure State Preserved (AC-012)**: Payment failure preserves unpaid order status and returns "Payment failed, you were not charged".
- [ ] **Test Mode Configuration**: Test keys (`sk_test_...`) and test payment method tokens used in all tests and local environments.
