# Specialist Pack: Payments & Idempotency Instructions

Source Grounding: Virtual Office Handbook Chapter 5.1.2 (AC-011, AC-012), Chapter 7.1.6 (API Standards), Chapter 12.1.3 & 12.1.4 (Backend Reliability and Security), Chapter 12.3.4 (Backend Procedure), Chapter 19.4 (Resilience Patterns), Chapter 30.1.1 (Testing).

## 1. Idempotency Key Handling
*Grounded in Handbook Chapter 7.1.6 & 19.4*:
1. Every POST request that creates a financial transaction, checkout session, charge, or order MUST require an `Idempotency-Key` HTTP header.
2. Store the key in an `idempotency_keys` table alongside a cryptographic hash of the request payload (SHA-256) and user ID.
3. If an incoming request contains a recognized `Idempotency-Key`:
   - If status is `COMPLETED`: Return the cached HTTP status code and response body immediately without re-executing business logic or gateway calls.
   - If status is `IN_PROGRESS`: Return HTTP `409 Conflict` or `425 Too Early` with a `Retry-After: 2` header to prevent concurrent race conditions.
   - If request payload hash does not match the stored hash: Return HTTP `422 Unprocessable Entity` ("Idempotency key reused with different payload").
4. Non-handbook addition [EXPLICIT EXTENSION]: Store key TTL with a 24-hour expiration window (`expires_at = datetime('now', '+24 hours')`).

## 2. Zero Raw Card Data Storage (PCI DSS Compliance)
*Grounded in Handbook Chapter 12.1.4 (OWASP Security & Data Minimization)*:
1. NEVER accept, process, transmit, or store raw 16-digit Primary Account Numbers (PAN), CVVs, CVCs, or PINs in your backend database or log files.
2. All card collection must occur via client-side gateway tokens or hosted checkout elements (e.g. Stripe Elements, Razorpay standard checkout).
3. The backend only accepts opaque gateway payment method tokens (e.g., `pm_card_visa`, `tok_12345`).
4. Allowed persistent metadata: `gateway_payment_method_id`, card brand (e.g., `visa`), last 4 digits (`last4`), expiration month, expiration year.

## 3. Webhook Signature Verification and Replay Safety
*Grounded in Handbook Chapter 12.1.4 (OWASP: "verify webhooks' signatures") & 12.3.4 (Item 5)*:
1. Every payment webhook endpoint (e.g., `/api/v1/payments/webhook`) MUST verify the cryptographic signature sent by the gateway provider using the shared webhook signing secret.
2. Read the raw, unparsed request body for signature calculation; never compute HMAC on parsed/serialized JSON objects.
3. Replay Safety [EXPLICIT EXTENSION beyond handbook text]:
   - Extract the timestamp header (e.g., `t=` in `Stripe-Signature`).
   - Compute current drift: `|current_time - event_timestamp|`. If drift exceeds 300 seconds (5 minutes), reject with HTTP `400 Bad Request` ("Webhook timestamp expired").
4. Deduplication: Store processed `webhook_event_id` in a `processed_webhooks` table. If the event ID has already been recorded, acknowledge with HTTP `200 OK` immediately without repeating actions.

## 4. Test-Mode Gateway Integration
*Grounded in Handbook Chapter 30.1.1 ("test-mode payments")*:
1. Production secret keys are strictly forbidden. Use test API keys (`sk_test_...`) provided via environment variables (`PAYMENT_GATEWAY_SECRET_KEY`).
2. Automated tests must utilize simulated test card tokens (e.g., `tok_visa`, `pm_card_visa` for success; `tok_chargeDeclined` for declines).

## 5. Failure and Retry Paths
*Grounded in Handbook Chapter 5.1.2 (AC-012) & Chapter 12.1.3*:
1. Unhappy paths are mandatory:
   - *AC-012*: Given the payment gateway returns a failure (e.g., card declined, insufficient funds), when the user returns to the app, then the order/fee still shows as unpaid and a message states "Payment failed, you were not charged".
2. Outbound gateway retries: Apply exponential backoff with jitter ONLY for idempotent network timeouts or 5xx server errors. NEVER retry 4xx client errors (card declined, invalid currency, expired card).

## 6. Reconciliation and Refunds
*Grounded in Handbook Chapter 12.1.3 (Outbox pattern) & Chapter 19*:
1. Write the payment state update and ledger event atomically in the same database transaction.
2. Refund endpoints (`POST /api/v1/payments/{id}/refund`) require an `Idempotency-Key`, must link to the original transaction ID, and must record refund reason and operator/user ID.
