"""
Reference Notifications Outbox Worker Implementation
Grounded in Handbook Chapter 12.1.3 and Chapter 19.
"""
import html
from typing import Dict, Any, Optional

def render_safe_email_template(raw_template_html: str, context: Dict[str, str]) -> str:
    """Escapes context variables to prevent HTML/XSS injection into emails."""
    safe_context = {k: html.escape(str(v)) for k, v in context.items()}
    output = raw_template_html
    for k, v in safe_context.items():
        output = output.replace(f"{{{{{k}}}}}", v)
    return output

def should_send_to_recipient(recipient: str, suppression_set: set) -> bool:
    """Checks whether recipient is suppressed due to bounce, complaint, or opt-out."""
    return recipient.strip().lower() not in suppression_set
