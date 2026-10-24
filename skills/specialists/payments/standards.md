# Specialist Pack: Payments Standards

**Source Grounding**: Virtual Office Handbook Chapter 7.1.6, Chapter 12.1.3-12.1.4, Chapter 19.

## 1. API Contract Requirements
1. **Header**: `Idempotency-Key: <UUIDv4 | string (16-128 chars)>` required on:
   - `POST /api/v1/checkout/sessions`
   - `POST /api/v1/payments/charges`
   - `POST /api/v1/payments/{id}/refund`
   - **Provenance**: IETF Draft `draft-ietf-httpapi-idempotency-key-header-06` (2024-03)
   - **Source URL**: https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header-06
   - **Version**: draft-06 | **Date**: 2024-03-12 | **Status**: VERIFIED

2. **Error Format**: RFC 9457 Problem Details for HTTP APIs:
   ```json
   {
     "type": "https://api.example.com/errors/payment-declined",
     "title": "Payment Declined",
     "status": 402,
     "detail": "Payment failed, you were not charged.",
     "code": "card_declined"
   }
   ```
   - **Provenance**: RFC 9457 (Obsoletes RFC 7807)
   - **Source URL**: https://www.rfc-editor.org/rfc/rfc9457.html
   - **Version**: RFC 9457 | **Date**: 2023-07-01 | **Status**: VERIFIED

3. **Webhook Verification Header**:
   - `Stripe-Signature` or `X-Signature-SHA256`: `t=<timestamp>,v1=<signature>`
   - Signature computed via HMAC-SHA256 using the webhook signing secret over `t + "." + payload`.
   - Verified using constant-time comparison (`hmac.compare_digest`) and enforcing timestamp drift tolerance `abs(now - t) <= 300s`.
   - **Provenance**: Stripe Webhook Signatures Specification & RFC 2104 (HMAC)
   - **Source URL**: https://docs.stripe.com/webhooks & https://docs.stripe.com/webhooks/signatures & https://www.rfc-editor.org/rfc/rfc2104
   - **Version**: Stripe API 2024-09 | **Date**: 2024-09-01 | **Status**: VERIFIED

4. **HTTP Semantics & Status Codes (RFC 9110)**:
   - Status codes for payment transactions (200 OK, 201 Created, 400 Bad Request, 402 Payment Required, 409 Conflict) strictly conform to RFC 9110 (HTTP Semantics, obsoletes RFC 7231).
   - **Provenance**: RFC 9110 (HTTP Semantics)
   - **Source URL**: https://www.rfc-editor.org/rfc/rfc9110.html
   - **Version**: RFC 9110 | **Date**: 2022-06-01 | **Status**: VERIFIED

## 2. Database Schema Standard
Tables required for compliance:
- `idempotency_keys`:
  - `key` (TEXT PRIMARY KEY)
  - `request_hash` (TEXT NOT NULL)
  - `status` (TEXT NOT NULL CHECK(status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')))
  - `status_code` (INTEGER)
  - `response_body` (TEXT)
  - `created_at` (TEXT NOT NULL DEFAULT (datetime('now')))
  - `expires_at` (TEXT NOT NULL)
- `payment_transactions`:
  - `id` (TEXT PRIMARY KEY)
  - `order_id` (TEXT NOT NULL)
  - `gateway_reference` (TEXT UNIQUE)
  - `amount_cents` (INTEGER NOT NULL)
  - `currency` (TEXT NOT NULL)
  - `status` (TEXT NOT NULL CHECK(status IN ('pending', 'succeeded', 'failed', 'refunded')))
  - `payment_method_token` (TEXT NOT NULL)
  - `card_brand` (TEXT)
  - `card_last4` (TEXT)
  - `created_at` (TEXT NOT NULL DEFAULT (datetime('now')))
- `processed_webhooks`:
  - `event_id` (TEXT PRIMARY KEY)
  - `event_type` (TEXT NOT NULL)
  - `processed_at` (TEXT NOT NULL DEFAULT (datetime('now')))
- **Provenance**: Autonoma Architecture Team Reference DDL
- **Status**: [UNVERIFIED] (Internal SQLite reference pattern; no external RFC mandates these exact column identifiers)

## 3. Security Constraints (PCI DSS)
- Zero column named `card_number`, `pan`, `cvv`, `cvc`, `security_code`.
- RegEx scan during Judge review checks that code contains no credit card pattern matches (`\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b`).
- Storage of raw PAN is strictly forbidden across application database, logs, and test fixtures.
- **Provenance**: PCI DSS v4.0.1 (Requirements 3.2, 3.4)
- **Source URL**: https://www.pcisecuritystandards.org/document_library/
- **Version**: PCI DSS v4.0.1 | **Date**: 2024-06-11 | **Status**: VERIFIED
