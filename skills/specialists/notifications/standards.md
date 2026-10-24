# Specialist Pack: Notifications Standards

**Source Grounding**: Virtual Office Handbook Chapter 12.1.3, Chapter 19, Chapter 3.

## 1. Outbox Table Schema
```sql
CREATE TABLE IF NOT EXISTS notification_outbox (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL CHECK(channel IN ('email', 'sms', 'push')),
    recipient TEXT NOT NULL,
    subject TEXT,
    body_text TEXT NOT NULL,
    body_html TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'processing', 'sent', 'failed', 'suppressed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,
    next_retry_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS suppressed_recipients (
    recipient TEXT PRIMARY KEY,
    reason TEXT NOT NULL CHECK(reason IN ('hard_bounce', 'complaint', 'opt_out')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```
- **Provenance**: Transactional Outbox Pattern (Chris Richardson, Microservices Patterns)
- **Source URL**: https://microservices.io/patterns/data/transactional-outbox.html
- **Version**: Pattern Reference 2023 | **Date**: 2023-05-10 | **Status**: [UNVERIFIED] (Architectural pattern is verified; specific SQLite DDL identifiers are internal conventions)

## 2. Webhook & Gateway Callback Security (Twilio Webhook Security)
- Webhook signature validation via HMAC-SHA1 / HMAC-SHA256 signature verification over full URL + POST parameters.
- Replay prevention using timestamp validation and SSL/TLS verification per RFC 9110 (HTTP Semantics, obsoletes RFC 7231).
- **Provenance**: Twilio Webhook Security Documentation & RFC 9110
- **Source URL**: https://www.twilio.com/docs/usage/webhooks/webhooks-security & https://www.rfc-editor.org/rfc/rfc9110.html
- **Version**: Twilio Security Docs 2024 / RFC 9110 | **Date**: 2024-03-15 / 2022-06-01 | **Status**: VERIFIED

## 3. Unsubscribe Headers Standard
```http
List-Unsubscribe: <https://api.example.com/api/v1/notifications/unsubscribe?token=...>, <mailto:unsubscribe@example.com?subject=unsubscribe>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```
- **Provenance**: RFC 2369 (List-Unsubscribe) & RFC 8058 (One-Click Unsubscribe)
- **Source URL**: https://www.rfc-editor.org/rfc/rfc8058.html & https://www.rfc-editor.org/rfc/rfc2369.html
- **Version**: RFC 8058 / RFC 2369 | **Date**: 2017-01-15 / 1998-07-01 | **Status**: VERIFIED
