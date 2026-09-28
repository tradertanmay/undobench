"""Standard invariant checkers for RecoverBench domains."""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Tuple


def check_balance_conservation(sandbox: Any, expected_sum: float, accounts: List[str]) -> Tuple[bool, str]:
    """Verify sum of balances across accounts equals expected total."""
    actual_sum = 0.0
    for acc in accounts:
        bal = sandbox.query_account_balance(acc)
        if bal is None:
            return False, f"Account '{acc}' missing during conservation check"
        actual_sum += bal
    if abs(actual_sum - expected_sum) > 1e-4:
        return False, f"Balance conservation violated: expected sum {expected_sum}, got {actual_sum}"
    return True, f"Balance conservation valid (sum={actual_sum})"


def check_double_entry_conservation(sandbox: Any) -> Tuple[bool, str]:
    """Verify sum of debits == sum of credits in double-entry ledger."""
    if hasattr(sandbox, "verify_conservation_invariant"):
        ok = sandbox.verify_conservation_invariant()
        if not ok:
            return False, "Double-entry accounting invariant violated: debits != credits"
        return True, "Double-entry accounting invariant satisfied"
    return True, "No double-entry ledger to check"


def check_git_cleanliness(sandbox: Any) -> Tuple[bool, str]:
    """Verify Git repository working tree is clean."""
    if hasattr(sandbox, "is_working_tree_clean"):
        clean = sandbox.is_working_tree_clean()
        if not clean:
            return False, "Git working tree is dirty after execution"
        return True, "Git working tree is clean"
    return True, "Not a git sandbox"


def check_non_negative_balance(sandbox: Any) -> Tuple[bool, str]:
    """Verify account balances do not dip below zero."""
    if hasattr(sandbox, "get_full_state"):
        st = sandbox.get_full_state()
        accounts = st.get("accounts", {})
        for acc, bal in accounts.items():
            if isinstance(bal, (int, float)) and bal < 0:
                return False, f"Solvency violation: account '{acc}' balance is negative ({bal})"
    return True, "All account balances non-negative"


INVARIANT_REGISTRY: Dict[str, Callable[..., Tuple[bool, str]]] = {
    "balance_conservation": check_balance_conservation,
    "double_entry_conservation": check_double_entry_conservation,
    "git_cleanliness": check_git_cleanliness,
    "non_negative_balance": check_non_negative_balance,
}
