"""SQLite relational database domain sandbox."""

from __future__ import annotations
import os
import shutil
import sqlite3
import tempfile
from typing import Any, Dict, List, Optional


class SQLiteSandbox:
    """Manages an isolated SQLite relational state for database tasks."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self._tmp_dir = tempfile.mkdtemp(prefix="rb_sqlite_")
            self.db_path = os.path.join(self._tmp_dir, "benchmark.db")
        else:
            self._tmp_dir = None
            self.db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                balance REAL NOT NULL,
                status TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customer_profiles (
                customer_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                tier TEXT NOT NULL,
                credits INTEGER DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                item_id TEXT PRIMARY KEY,
                quantity INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def seed_account(self, account_id: str, name: str, balance: float, status: str = "ACTIVE") -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO accounts (account_id, name, balance, status) VALUES (?, ?, ?, ?)",
            (account_id, name, balance, status),
        )
        conn.commit()
        conn.close()

    def seed_customer(self, customer_id: str, name: str, tier: str, credits: int = 0) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO customer_profiles (customer_id, name, tier, credits) VALUES (?, ?, ?, ?)",
            (customer_id, name, tier, credits),
        )
        conn.commit()
        conn.close()

    # --- Tool Callables (Exposed to Agents via ToolProxy) ---

    def deduct_account_balance(self, account_id: str, amount: float) -> Dict[str, Any]:
        """Tool: Deduct amount from account."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT balance FROM accounts WHERE account_id = ?", (account_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Account {account_id} not found")
        curr_bal = float(row[0])
        new_bal = curr_bal - amount
        cur.execute("UPDATE accounts SET balance = ? WHERE account_id = ?", (new_bal, account_id))
        conn.commit()
        conn.close()
        return {"account_id": account_id, "previous_balance": curr_bal, "new_balance": new_bal}

    def credit_account_balance(self, account_id: str, amount: float) -> Dict[str, Any]:
        """Tool: Credit amount to account."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT balance FROM accounts WHERE account_id = ?", (account_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Account {account_id} not found")
        curr_bal = float(row[0])
        new_bal = curr_bal + amount
        cur.execute("UPDATE accounts SET balance = ? WHERE account_id = ?", (new_bal, account_id))
        conn.commit()
        conn.close()
        return {"account_id": account_id, "previous_balance": curr_bal, "new_balance": new_bal}

    def upgrade_customer_tier(self, customer_id: str, new_tier: str) -> Dict[str, Any]:
        """Tool: Upgrade customer tier."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT tier FROM customer_profiles WHERE customer_id = ?", (customer_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Customer {customer_id} not found")
        old_tier = row[0]
        cur.execute("UPDATE customer_profiles SET tier = ? WHERE customer_id = ?", (new_tier, customer_id))
        conn.commit()
        conn.close()
        return {"customer_id": customer_id, "old_tier": old_tier, "new_tier": new_tier}

    def write_audit_record(self, entity_id: str, action: str, details: str = "") -> Dict[str, Any]:
        """Tool: Insert audit record."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO audit_records (entity_id, action, details) VALUES (?, ?, ?)",
            (entity_id, action, details),
        )
        record_id = cur.lastrowid
        conn.commit()
        conn.close()
        return {"audit_id": record_id, "entity_id": entity_id, "action": action}

    def create_order(self, order_id: str, customer_id: str, amount: float, status: str = "CONFIRMED") -> Dict[str, Any]:
        """Tool: Create a customer order record."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO orders (order_id, customer_id, amount, status) VALUES (?, ?, ?, ?)",
            (order_id, customer_id, amount, status),
        )
        conn.commit()
        conn.close()
        return {"order_id": order_id, "customer_id": customer_id, "amount": amount, "status": status}

    def reserve_inventory(self, item_id: str, quantity: int) -> Dict[str, Any]:
        """Tool: Deduct stock from inventory."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT quantity FROM inventory WHERE item_id = ?", (item_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Item {item_id} not found")
        curr_qty = row[0]
        if curr_qty < quantity:
            conn.close()
            raise ValueError(f"Insufficient inventory for {item_id}")
        new_qty = curr_qty - quantity
        cur.execute("UPDATE inventory SET quantity = ? WHERE item_id = ?", (new_qty, item_id))
        conn.commit()
        conn.close()
        return {"item_id": item_id, "previous_quantity": curr_qty, "reserved": quantity, "new_quantity": new_qty}

    def seed_inventory(self, item_id: str, quantity: int) -> None:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO inventory (item_id, quantity) VALUES (?, ?)", (item_id, quantity))
        conn.commit()
        conn.close()

    def apply_schema_migration(self, version: int) -> Dict[str, Any]:
        """Tool: Record schema migration execution."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        conn.commit()
        conn.close()
        return {"version": version, "status": "APPLIED"}

    def allocate_dividend(self, account_id: str, dividend: float) -> Dict[str, Any]:
        """Tool: Read-modify-write dividend allocation to account."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT balance FROM accounts WHERE account_id = ?", (account_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Account {account_id} not found")
        prev = float(row[0])
        new_bal = prev + dividend
        cur.execute("UPDATE accounts SET balance = ? WHERE account_id = ?", (new_bal, account_id))
        conn.commit()
        conn.close()
        return {"account_id": account_id, "previous_balance": prev, "dividend": dividend, "new_balance": new_bal}

    # --- Oracle Inspection Methods ---

    def query_account_balance(self, account_id: str) -> Optional[float]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT balance FROM accounts WHERE account_id = ?", (account_id,))
        row = cur.fetchone()
        conn.close()
        return float(row[0]) if row else None

    def query_customer_tier(self, customer_id: str) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT tier FROM customer_profiles WHERE customer_id = ?", (customer_id,))
        row = cur.fetchone()
        conn.close()
        return str(row[0]) if row else None

    def query_audit_count(self, entity_id: str, action: Optional[str] = None) -> int:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        if action:
            cur.execute("SELECT COUNT(*) FROM audit_records WHERE entity_id = ? AND action = ?", (entity_id, action))
        else:
            cur.execute("SELECT COUNT(*) FROM audit_records WHERE entity_id = ?", (entity_id,))
        count = cur.fetchone()[0]
        conn.close()
        return int(count)

    def get_full_state(self) -> Dict[str, Any]:
        """Oracle snapshot of entire relational state."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT account_id, balance FROM accounts")
        accounts = {row[0]: float(row[1]) for row in cur.fetchall()}
        cur.execute("SELECT customer_id, tier, credits FROM customer_profiles")
        customers = {row[0]: {"tier": row[1], "credits": row[2]} for row in cur.fetchall()}
        cur.execute("SELECT COUNT(*) FROM audit_records")
        audits = cur.fetchone()[0]
        cur.execute("SELECT order_id, customer_id, amount, status FROM orders")
        orders = {row[0]: {"customer_id": row[1], "amount": float(row[2]), "status": row[3]} for row in cur.fetchall()}
        cur.execute("SELECT item_id, quantity FROM inventory")
        inventory = {row[0]: int(row[1]) for row in cur.fetchall()}
        cur.execute("SELECT version FROM schema_migrations")
        migrations = [row[0] for row in cur.fetchall()]
        conn.close()
        return {
            "accounts": accounts,
            "customers": customers,
            "audit_count": audits,
            "orders": orders,
            "inventory": inventory,
            "migrations": migrations,
        }

    def cleanup(self) -> None:
        if self._tmp_dir and os.path.exists(self._tmp_dir):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
