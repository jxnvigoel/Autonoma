# Specialist Pack: Notifications Standards

Source Grounding: Handbook Chapter 12.1.3, Chapter 19.

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

## 2. Unsubscribe Headers Standard
```http
List-Unsubscribe: <https://api.example.com/api/v1/notifications/unsubscribe?token=...>, <mailto:unsubscribe@example.com?subject=unsubscribe>
List-Unsubscribe-Post: List-Unsubscribe=One-Click
```
