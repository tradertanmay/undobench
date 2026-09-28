"""CRM & Enterprise Workflow domain sandbox."""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class QueuedEventRecord:
    event_id: str
    event_type: str
    target_id: str
    payload: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class CRMSandbox:
    """Manages CRM customer leads, status workflows, and queued outbound events."""

    def __init__(self):
        self.leads: Dict[str, Dict[str, Any]] = {}
        self.outbound_event_queue: List[QueuedEventRecord] = []
        self.opportunities: Dict[str, Dict[str, Any]] = {}
        self.rep_quotas: Dict[str, float] = {}
        self.accounts: Dict[str, Dict[str, Any]] = {}

    def seed_lead(self, lead_id: str, name: str, email: str, status: str = "NEW") -> None:
        self.leads[lead_id] = {
            "lead_id": lead_id,
            "name": name,
            "email": email,
            "status": status,
        }

    def seed_opportunity(self, opp_id: str, stage: str, deal_value: float, rep_id: str) -> None:
        self.opportunities[opp_id] = {
            "opp_id": opp_id,
            "stage": stage,
            "deal_value": deal_value,
            "rep_id": rep_id,
        }
        self.rep_quotas.setdefault(rep_id, 0.0)

    def seed_account(self, account_id: str, name: str, status: str = "ACTIVE", sla_tier: str = "STANDARD") -> None:
        self.accounts[account_id] = {
            "account_id": account_id,
            "name": name,
            "status": status,
            "sla_tier": sla_tier,
            "merged_into": None,
        }

    # --- Tool Callables ---

    def convert_lead_status(self, lead_id: str, new_status: str) -> Dict[str, Any]:
        """Tool: Transition lead workflow status (e.g. NEW -> ACTIVE_CUSTOMER)."""
        if lead_id not in self.leads:
            raise ValueError(f"Lead {lead_id} not found")
        lead = self.leads[lead_id]
        old_status = lead["status"]
        lead["status"] = new_status
        return {"lead_id": lead_id, "previous_status": old_status, "new_status": new_status}

    def advance_opportunity_stage(self, opp_id: str, stage: str, deal_value: float) -> Dict[str, Any]:
        """Tool: Progress sales opportunity to stage (e.g. CLOSED_WON)."""
        if opp_id not in self.opportunities:
            raise ValueError(f"Opportunity {opp_id} not found")
        opp = self.opportunities[opp_id]
        opp["stage"] = stage
        opp["deal_value"] = deal_value
        return {"opp_id": opp_id, "stage": stage, "deal_value": deal_value}

    def update_rep_quota(self, rep_id: str, amount: float) -> Dict[str, Any]:
        """Tool: Credit sales representative quota attainment."""
        curr = self.rep_quotas.get(rep_id, 0.0)
        new_quota = curr + amount
        self.rep_quotas[rep_id] = new_quota
        return {"rep_id": rep_id, "previous_quota": curr, "new_quota": new_quota}

    def merge_customer_accounts(self, primary_id: str, secondary_id: str) -> Dict[str, Any]:
        """Tool: Merge secondary customer account into primary account."""
        if primary_id not in self.accounts or secondary_id not in self.accounts:
            raise ValueError("Both accounts must exist to merge")
        sec = self.accounts[secondary_id]
        sec["status"] = "MERGED"
        sec["merged_into"] = primary_id
        return {"primary_id": primary_id, "secondary_id": secondary_id, "status": "MERGED"}

    def renew_enterprise_sla(self, account_id: str, sla_tier: str) -> Dict[str, Any]:
        """Tool: Renew customer account SLA tier."""
        if account_id not in self.accounts:
            raise ValueError(f"Account {account_id} not found")
        acct = self.accounts[account_id]
        acct["sla_tier"] = sla_tier
        return {"account_id": account_id, "sla_tier": sla_tier, "status": "RENEWED"}

    def queue_welcome_sequence(self, lead_id: str, template: str = "welcome_v1") -> Dict[str, Any]:
        """Tool: Queue welcome email / onboarding sequence for converted lead."""
        if lead_id not in self.leads:
            raise ValueError(f"Lead {lead_id} not found")
        event_id = f"event_{len(self.outbound_event_queue) + 1}"
        record = QueuedEventRecord(
            event_id=event_id,
            event_type="WELCOME_SEQUENCE_QUEUED",
            target_id=lead_id,
            payload={"email": self.leads[lead_id]["email"], "template": template},
        )
        self.outbound_event_queue.append(record)
        return {"event_id": event_id, "lead_id": lead_id, "status": "QUEUED"}

    # --- Oracle Inspection Methods ---

    def query_lead_status(self, lead_id: str) -> Optional[str]:
        lead = self.leads.get(lead_id)
        return lead["status"] if lead else None

    def query_queued_event_count(self, lead_id: str, event_type: str = "WELCOME_SEQUENCE_QUEUED") -> int:
        return sum(1 for e in self.outbound_event_queue if e.target_id == lead_id and e.event_type == event_type)

    def get_full_state(self) -> Dict[str, Any]:
        return {
            "leads": self.leads.copy(),
            "queued_events_count": len(self.outbound_event_queue),
            "queued_events": [e.__dict__ for e in self.outbound_event_queue],
            "opportunities": self.opportunities.copy(),
            "rep_quotas": self.rep_quotas.copy(),
            "accounts": self.accounts.copy(),
        }
