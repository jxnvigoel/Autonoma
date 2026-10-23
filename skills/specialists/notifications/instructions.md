# Specialist Pack: Notifications Instructions

Source Grounding: Virtual Office Handbook Chapter 4.1.3 (External Integrations), Chapter 12.1.3 (Outbound Calls, Reliability & Queues), Chapter 19.3-19.4 (Queues, Retries, Resilience).

## 1. Outbound Delivery Architecture
*Grounded in Handbook Chapter 12.1.3 & 19.3*:
1. Never send emails or SMS synchronously inside HTTP request handlers. Enqueue delivery jobs to an outbox table or background task queue.
2. Handlers insert notification records (`status='pending'`) inside the same database transaction as the business trigger.
3. Background workers poll/consume tasks and communicate with email/SMS gateways (e.g. SendGrid, AWS SES, Twilio).

## 2. Safe Templating and Content Encoding
*Grounded in Handbook Chapter 12.1.4 (Input Validation & XSS Prevention)*:
1. All dynamic variables in notification templates must be HTML-escaped automatically before rendering.
2. Plain-text alternative bodies must be generated alongside HTML emails to ensure accessibility and spam filter compliance.

## 3. Retries, Jitter, and Dead-Letter Queue (DLQ)
*Grounded in Handbook Chapter 12.1.3 & 19.4*:
1. Retry only transient network failures and 5xx gateway errors. Never retry 4xx errors (invalid email format, unallocated phone number).
2. Use exponential backoff with randomized jitter (e.g., base delays of 10s, 60s, 300s).
3. If an outbound notification fails 3 consecutive times, mark it `FAILED` and record the terminal error in the Dead-Letter Queue (DLQ) table for operational review.

## 4. Bounce, Complaint, and Delivery Webhook Handling
*Explicit Non-Handbook Standard [EXPLICIT EXTENSION]*:
1. Provide a webhook endpoint (e.g., `/api/v1/notifications/webhooks/delivery`) to receive bounce and complaint events from mail gateways.
2. Permanent bounces (hard bounces) and spam complaints must immediately add the recipient's email address to a `suppressed_recipients` table.
3. Prior to attempting outbound delivery, workers must check the suppression list; any send to a suppressed address must be aborted with status `SUPPRESSED`.

## 5. Recipient Rate Limiting
*Grounded in Handbook Chapter 19.4 (Resilience Patterns: Rate Limiting)*:
1. Enforce per-user/per-recipient rate limits to avoid mail storms and provider throttling (e.g. maximum 10 emails/SMS per user per hour for non-critical alerts).
2. Critical security notifications (password reset, 2FA codes) bypass marketing limits but are rate-limited to 5 per 15 minutes.

## 6. Opt-Out and Compliance (Unsubscribe)
*Explicit Non-Handbook Standard [EXPLICIT EXTENSION]*:
1. Non-transactional emails must include both:
   - A visible unsubscribe link in the email footer.
   - Standard `List-Unsubscribe` and `List-Unsubscribe-Post` email headers for 1-click unsubscribe.
2. Unsubscribe endpoints must not require the user to log in or enter credentials to opt out.
