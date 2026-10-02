"""Payments & Ledger domain sandbox with idempotency and double-entry accounting."""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RefundRecord:
    refund_id: str
    charge_id: str
    amount_cents: int
    idempotency_key: Optional[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class LedgerJournalEntry:
    entry_id: str
    debit_account: str
    credit_account: str
    amount_cents: int
    memo: str
    is_compensating: bool = False
    timestamp: float = field(default_factory=time.time)


class PaymentGatewaySimulator:
    """Simulates a Stripe-like payment gateway with idempotency key deduplication."""

    def __init__(self):
        self.charges: Dict[str, Dict[str, Any]] = {}
        self.refunds: List[RefundRecord] = []
        self.idempotency_records: Dict[str, Dict[str, Any]] = {}

    def seed_charge(self, charge_id: str, customer_id: str, amount_cents: int, status: str = "SUCCEEDED") -> None:
        self.charges[charge_id] = {
            "charge_id": charge_id,
            "customer_id": customer_id,
            "amount_cents": amount_cents,
            "amount_refunded_cents": 0,
            "status": status,
        }

    # --- Tool Callables ---

    def refund_charge(
        self,
        charge_id: str,
        amount_cents: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool: Issue refund on an existing charge with optional idempotency key."""
        if idempotency_key and idempotency_key in self.idempotency_records:
            # Idempotent response: return previously recorded result
            cached = self.idempotency_records[idempotency_key]
            return {**cached, "idempotent_replay": True}

        if charge_id not in self.charges:
            raise ValueError(f"Charge {charge_id} not found")

        ch = self.charges[charge_id]
        refund_id = f"re_{uuid.uuid4().hex[:12]}"
        ch["amount_refunded_cents"] += amount_cents

        record = RefundRecord(
            refund_id=refund_id,
            charge_id=charge_id,
            amount_cents=amount_cents,
            idempotency_key=idempotency_key,
        )
        self.refunds.append(record)

        result = {
            "refund_id": refund_id,
            "charge_id": charge_id,
            "amount_cents": amount_cents,
            "total_refunded_cents": ch["amount_refunded_cents"],
            "status": "SUCCEEDED",
        }
        if idempotency_key:
            self.idempotency_records[idempotency_key] = result
        return result

    def disburse_split_payout(
        self,
        payout_id: str,
        merchant_id: str,
        amount_cents: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool: Disburse payout split to merchant account."""
        if idempotency_key and idempotency_key in self.idempotency_records:
            return {**self.idempotency_records[idempotency_key], "idempotent_replay": True}
        res = {"payout_id": payout_id, "merchant_id": merchant_id, "amount_cents": amount_cents, "status": "PAID"}
        if idempotency_key:
            self.idempotency_records[idempotency_key] = res
        return res

    def process_subscription_renewal(
        self,
        sub_id: str,
        plan_id: str,
        amount_cents: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool: Process recurring subscription billing charge."""
        if idempotency_key and idempotency_key in self.idempotency_records:
            return {**self.idempotency_records[idempotency_key], "idempotent_replay": True}
        res = {"sub_id": sub_id, "plan_id": plan_id, "amount_cents": amount_cents, "status": "RENEWED"}
        if idempotency_key:
            self.idempotency_records[idempotency_key] = res
        return res

    def execute_wire_transfer(
        self,
        wire_id: str,
        source_curr: str,
        target_curr: str,
        amount_cents: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Tool: Execute cross-currency international wire transfer."""
        if idempotency_key and idempotency_key in self.idempotency_records:
            return {**self.idempotency_records[idempotency_key], "idempotent_replay": True}
        res = {"wire_id": wire_id, "source": source_curr, "target": target_curr, "amount_cents": amount_cents, "status": "SETTLED"}
        if idempotency_key:
            self.idempotency_records[idempotency_key] = res
        return res

    # --- Oracle Inspection Methods ---

    def query_charge_refunded_amount(self, charge_id: str) -> int:
        ch = self.charges.get(charge_id)
        return ch["amount_refunded_cents"] if ch else 0

    def query_refund_count(self, charge_id: str) -> int:
        return sum(1 for r in self.refunds if r.charge_id == charge_id)

    def get_full_state(self) -> Dict[str, Any]:
        return {
            "charges": self.charges,
            "total_refunds_count": len(self.refunds),
            "refunds": [r.__dict__ for r in self.refunds],
        }


class DoubleEntryLedgerSandbox:
    """Immutable double-entry accounting ledger with invariant checking."""

    def __init__(self):
        self.journal: List[LedgerJournalEntry] = []
        self.account_balances: Dict[str, int] = {}  # account -> balance in cents

    def seed_account(self, account_name: str, balance_cents: int) -> None:
        self.account_balances[account_name] = balance_cents

    # --- Tool Callables ---

    def post_journal_entry(
        self,
        debit_account: str,
        credit_account: str,
        amount_cents: int,
        memo: str = "",
        is_compensating: bool = False,
    ) -> Dict[str, Any]:
        """Tool: Post a double-entry transaction debiting one account and crediting another."""
        if amount_cents <= 0:
            raise ValueError("Amount must be positive")

        entry_id = f"entry_{len(self.journal) + 1}"
        entry = LedgerJournalEntry(
            entry_id=entry_id,
            debit_account=debit_account,
            credit_account=credit_account,
            amount_cents=amount_cents,
            memo=memo,
            is_compensating=is_compensating,
        )
        self.journal.append(entry)

        # Update accounts
        self.account_balances[debit_account] = self.account_balances.get(debit_account, 0) + amount_cents
        self.account_balances[credit_account] = self.account_balances.get(credit_account, 0) - amount_cents

        return {
            "entry_id": entry_id,
            "debit_account": debit_account,
            "credit_account": credit_account,
            "amount_cents": amount_cents,
            "is_compensating": is_compensating,
        }

    # --- Oracle Invariant Checkers ---

    def verify_conservation_invariant(self) -> bool:
        """Fundamental invariant: sum of all debits must equal sum of all credits."""
        total_debits = sum(e.amount_cents for e in self.journal)
        total_credits = sum(e.amount_cents for e in self.journal)
        return total_debits == total_credits

    def query_account_balance(self, account_name: str) -> int:
        return self.account_balances.get(account_name, 0)

    def query_compensating_entries_count(self) -> int:
        return sum(1 for e in self.journal if e.is_compensating)

    def get_full_state(self) -> Dict[str, Any]:
        return {
            "account_balances": self.account_balances.copy(),
            "journal_length": len(self.journal),
            "journal": [e.__dict__ for e in self.journal],
        }
