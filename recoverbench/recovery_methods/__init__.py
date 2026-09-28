"""Recovery methods module for RecoverBench."""

from recoverbench.recovery_methods.base import RecoveryMethod
from recoverbench.recovery_methods.checkpoint import CheckpointResumeMethod
from recoverbench.recovery_methods.evoundo_adapter import EvoUndoAdapter
from recoverbench.recovery_methods.idempotency import IdempotencyKeyMethod
try:
    from recoverbench.recovery_methods.langgraph_native import LangGraphNativeMethod
except ImportError:
    LangGraphNativeMethod = None  # type: ignore
from recoverbench.recovery_methods.naive_retry import NaiveRetryMethod
from recoverbench.recovery_methods.saga import SagaRecoveryMethod
from recoverbench.recovery_methods.verify_before_retry import VerifyBeforeRetryMethod

RECOVERY_METHOD_REGISTRY = {
    # B0
    "b0": NaiveRetryMethod,
    "naive_retry": NaiveRetryMethod,
    "naive": NaiveRetryMethod,
    "naive_retry:v1": NaiveRetryMethod,
    # B1
    "b1": CheckpointResumeMethod,
    "checkpoint": CheckpointResumeMethod,
    "checkpoint:v1": CheckpointResumeMethod,
    # B2
    "b2": IdempotencyKeyMethod,
    "idempotency": IdempotencyKeyMethod,
    "idempotency:v1": IdempotencyKeyMethod,
    # B3
    "b3": SagaRecoveryMethod,
    "saga": SagaRecoveryMethod,
    "saga:v1": SagaRecoveryMethod,
    # B5
    "b5": EvoUndoAdapter,
    "evoundo": EvoUndoAdapter,
    "evoundo:rb1": EvoUndoAdapter,
    # B6
    "b6": VerifyBeforeRetryMethod,
    "verify_before_retry": VerifyBeforeRetryMethod,
    "verify_before_retry:v1": VerifyBeforeRetryMethod,
    "vbr": VerifyBeforeRetryMethod,
}

if LangGraphNativeMethod is not None:
    RECOVERY_METHOD_REGISTRY.update({
        "b4": LangGraphNativeMethod,
        "langgraph_native": LangGraphNativeMethod,
        "langgraph": LangGraphNativeMethod,
        "langgraph_native:v1": LangGraphNativeMethod,
    })

__all__ = [
    "RecoveryMethod",
    "NaiveRetryMethod",
    "CheckpointResumeMethod",
    "IdempotencyKeyMethod",
    "SagaRecoveryMethod",
    "LangGraphNativeMethod",
    "EvoUndoAdapter",
    "VerifyBeforeRetryMethod",
    "RECOVERY_METHOD_REGISTRY",
]
