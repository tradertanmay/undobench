"""Oracle module for RecoverBench."""

from recoverbench.oracle.invariants import INVARIANT_REGISTRY
from recoverbench.oracle.state_oracle import StateOracle

__all__ = ["StateOracle", "INVARIANT_REGISTRY"]
