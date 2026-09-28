"""Ticketing & Incident Operations domain sandbox."""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PagingDispatchRecord:
    page_id: str
    incident_id: str
    recipient: str
    urgency: str
    timestamp: float = field(default_factory=time.time)


class IncidentDeskSandbox:
    """Manages incident tickets and external on-call paging dispatches."""

    def __init__(self):
        self.incidents: Dict[str, Dict[str, Any]] = {}
        self.paging_log: List[PagingDispatchRecord] = []

    def seed_incident(
        self,
        incident_id: str,
        title: str,
        severity: str = "LOW",
        status: str = "OPEN",
        assignee: Optional[str] = None,
    ) -> None:
        self.incidents[incident_id] = {
            "incident_id": incident_id,
            "title": title,
            "severity": severity,
            "status": status,
            "assignee": assignee,
        }

    # --- Tool Callables ---

    def update_incident_status(
        self,
        incident_id: str,
        new_severity: Optional[str] = None,
        new_status: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool: Update incident severity, status, or assignee."""
        if incident_id not in self.incidents:
            raise ValueError(f"Incident {incident_id} not found")
        inc = self.incidents[incident_id]
        if new_severity:
            inc["severity"] = new_severity
        if new_status:
            inc["status"] = new_status
        if assignee:
            inc["assignee"] = assignee
        return inc.copy()

    def dispatch_oncall_page(self, incident_id: str, oncall_engineer: str, urgency: str = "HIGH") -> Dict[str, Any]:
        """Tool: Page the on-call engineer via phone/pager alert."""
        if incident_id not in self.incidents:
            raise ValueError(f"Incident {incident_id} not found")
        page_id = f"page_{len(self.paging_log) + 1}"
        record = PagingDispatchRecord(
            page_id=page_id,
            incident_id=incident_id,
            recipient=oncall_engineer,
            urgency=urgency,
        )
        self.paging_log.append(record)
        return {
            "page_id": page_id,
            "incident_id": incident_id,
            "status": "DISPATCHED",
            "recipient": oncall_engineer,
        }

    def assign_incident_team(self, incident_id: str, team_name: str) -> Dict[str, Any]:
        """Tool: Assign incident ownership to specialized engineering team."""
        if incident_id not in self.incidents:
            raise ValueError(f"Incident {incident_id} not found")
        self.incidents[incident_id]["assigned_team"] = team_name
        return {"incident_id": incident_id, "assigned_team": team_name}

    def resolve_incident(self, incident_id: str, resolution_note: str) -> Dict[str, Any]:
        """Tool: Mark incident as RESOLVED with post-mortem notes."""
        if incident_id not in self.incidents:
            raise ValueError(f"Incident {incident_id} not found")
        self.incidents[incident_id]["status"] = "RESOLVED"
        self.incidents[incident_id]["resolution_note"] = resolution_note
        return {"incident_id": incident_id, "status": "RESOLVED", "resolution_note": resolution_note}

    def dispatch_resolution_notice(self, incident_id: str, customer_email: str) -> Dict[str, Any]:
        """Tool: Send customer notification that incident has been resolved."""
        page_id = f"notice_{len(self.paging_log) + 1}"
        record = PagingDispatchRecord(page_id=page_id, incident_id=incident_id, recipient=customer_email, urgency="NORMAL")
        self.paging_log.append(record)
        return {"notice_id": page_id, "incident_id": incident_id, "customer_email": customer_email, "status": "DISPATCHED"}

    def escalate_incident_sla(self, incident_id: str, tier: str) -> Dict[str, Any]:
        """Tool: Escalate incident to higher SLA response tier."""
        if incident_id not in self.incidents:
            raise ValueError(f"Incident {incident_id} not found")
        self.incidents[incident_id]["sla_tier"] = tier
        return {"incident_id": incident_id, "sla_tier": tier, "status": "ESCALATED"}

    # --- Oracle Inspection Methods ---

    def query_paging_count(self, incident_id: str) -> int:
        return sum(1 for p in self.paging_log if p.incident_id == incident_id)

    def query_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        return self.incidents.get(incident_id)

    def get_full_state(self) -> Dict[str, Any]:
        return {
            "incidents": self.incidents.copy(),
            "total_pages": len(self.paging_log),
            "paging_log": [p.__dict__ for p in self.paging_log],
        }
