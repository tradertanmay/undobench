"""Messaging & Notification domain sandbox with irreversible dispatch semantics."""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SentNotification:
    notification_id: str
    channel: str
    recipient: str
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class WebhookDelivery:
    delivery_id: str
    target_url: str
    event_type: str
    payload: Dict[str, Any]
    status_code: int = 200
    timestamp: float = field(default_factory=time.time)


@dataclass
class OnCallPage:
    page_id: str
    service: str
    alert_title: str
    severity: str
    timestamp: float = field(default_factory=time.time)


class MessagingNotificationSandbox:
    """Manages irreversible outbound communication channels (Slack, SMS, Webhooks, PagerDuty)."""

    def __init__(self):
        self.sent_notifications: List[SentNotification] = []
        self.webhook_deliveries: List[WebhookDelivery] = []
        self.pages: List[OnCallPage] = []
        self.idempotency_store: Dict[str, Dict[str, Any]] = {}

    # --- Tool Callables (Exposed to Agents via ToolProxy) ---

    def send_slack_alert(self, channel: str, message: str) -> Dict[str, Any]:
        """Tool: Post alert to Slack channel (Irreversible)."""
        notif_id = f"slack_{uuid.uuid4().hex[:10]}"
        notif = SentNotification(
            notification_id=notif_id,
            channel=channel,
            recipient=channel,
            content=message,
        )
        self.sent_notifications.append(notif)
        return {
            "notification_id": notif_id,
            "channel": channel,
            "status": "DELIVERED",
        }

    def broadcast_sms_notification(self, phone_number: str, text: str) -> Dict[str, Any]:
        """Tool: Dispatch SMS alert to recipient phone (Irreversible)."""
        notif_id = f"sms_{uuid.uuid4().hex[:10]}"
        notif = SentNotification(
            notification_id=notif_id,
            channel="SMS",
            recipient=phone_number,
            content=text,
        )
        self.sent_notifications.append(notif)
        return {
            "notification_id": notif_id,
            "recipient": phone_number,
            "status": "SENT",
        }

    def post_webhook_event(
        self,
        target_url: str,
        event_type: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool: Post webhook event to remote endpoint."""
        if idempotency_key and idempotency_key in self.idempotency_store:
            cached = self.idempotency_store[idempotency_key]
            return {**cached, "idempotent_replay": True}

        deliv_id = f"deliv_{uuid.uuid4().hex[:10]}"
        deliv = WebhookDelivery(
            delivery_id=deliv_id,
            target_url=target_url,
            event_type=event_type,
            payload=payload,
        )
        self.webhook_deliveries.append(deliv)
        result = {
            "delivery_id": deliv_id,
            "target_url": target_url,
            "event_type": event_type,
            "status_code": 200,
        }
        if idempotency_key:
            self.idempotency_store[idempotency_key] = result
        return result

    def page_oncall_engineer(self, service: str, alert_title: str, severity: str = "P1") -> Dict[str, Any]:
        """Tool: Dispatch high-urgency PagerDuty incident alert (Irreversible)."""
        page_id = f"page_{uuid.uuid4().hex[:10]}"
        page = OnCallPage(
            page_id=page_id,
            service=service,
            alert_title=alert_title,
            severity=severity,
        )
        self.pages.append(page)
        return {
            "page_id": page_id,
            "service": service,
            "severity": severity,
            "status": "DISPATCHED",
        }

    def send_batch_email(
        self,
        campaign_id: str,
        recipients: List[str],
        template_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool: Dispatch batch email campaign to multiple recipients."""
        if idempotency_key and idempotency_key in self.idempotency_store:
            return {**self.idempotency_store[idempotency_key], "idempotent_replay": True}

        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        for r in recipients:
            self.sent_notifications.append(
                SentNotification(
                    notification_id=f"email_{uuid.uuid4().hex[:8]}",
                    channel="EMAIL",
                    recipient=r,
                    content=f"Campaign {campaign_id} template {template_id}",
                )
            )
        res = {"batch_id": batch_id, "campaign_id": campaign_id, "recipients_count": len(recipients), "status": "DISPATCHED"}
        if idempotency_key:
            self.idempotency_store[idempotency_key] = res
        return res

    def acknowledge_page(self, page_id: str, engineer_id: str) -> Dict[str, Any]:
        """Tool: Acknowledge on-call incident page."""
        matched = [p for p in self.pages if p.page_id == page_id]
        if not matched:
            raise ValueError(f"Page {page_id} not found")
        return {"page_id": page_id, "acknowledged_by": engineer_id, "status": "ACKNOWLEDGED"}

    # --- Oracle Inspection Methods ---

    def query_sent_count(self, channel: Optional[str] = None) -> int:
        if not channel:
            return len(self.sent_notifications)
        return sum(1 for n in self.sent_notifications if n.channel == channel)

    def query_webhook_count(self, event_type: Optional[str] = None) -> int:
        if not event_type:
            return len(self.webhook_deliveries)
        return sum(1 for w in self.webhook_deliveries if w.event_type == event_type)

    def query_pages_count(self, severity: Optional[str] = None) -> int:
        if not severity:
            return len(self.pages)
        return sum(1 for p in self.pages if p.severity == severity)

    def get_full_state(self) -> Dict[str, Any]:
        return {
            "total_sent_notifications": len(self.sent_notifications),
            "sent_notifications": [n.__dict__ for n in self.sent_notifications],
            "total_webhooks": len(self.webhook_deliveries),
            "webhook_deliveries": [w.__dict__ for w in self.webhook_deliveries],
            "total_pages": len(self.pages),
            "pages": [p.__dict__ for p in self.pages],
        }

    def cleanup(self) -> None:
        self.sent_notifications.clear()
        self.webhook_deliveries.clear()
        self.pages.clear()
        self.idempotency_store.clear()
