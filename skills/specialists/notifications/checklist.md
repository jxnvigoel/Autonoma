# Specialist Pack: Notifications Checklist

- [ ] **Asynchronous Outbox**: Outbound sends enqueued to background outbox table rather than called inside web request thread.
- [ ] **Escaped Templates**: HTML email templates auto-escape dynamic variables. Plain-text version provided.
- [ ] **Exponential Backoff**: Retries use exponential backoff and jitter for transient 5xx errors.
- [ ] **DLQ on 3 Failures**: Terminal failures logged to dead-letter queue after 3 failed attempts.
- [ ] **Bounce Suppression**: Permanent bounces and complaints recorded to suppression table; suppressed addresses excluded from future sends.
- [ ] **Recipient Rate Limits**: Per-user limits enforced to prevent outbound flooding.
- [ ] **Unsubscribe / Opt-Out Support**: Unsubscribe header and 1-click links present for non-transactional mail.
