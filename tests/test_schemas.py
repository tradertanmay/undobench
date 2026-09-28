"""Unit tests for RecoverBench declarative schemas."""

import pytest
from recoverbench.schemas.fault import ExecutionBoundary, FaultSpec, Perturbation
from recoverbench.schemas.task import TaskSpec
from recoverbench.tasks.registry import TaskRegistry


def test_task_registry_dev_and_validation():
    task_ids = TaskRegistry.list_task_ids()
    assert len(task_ids) == 36
    assert "RB-DB-001" in task_ids
    assert "RB-PAY-001" in task_ids
    assert "RB-GIT-001" in task_ids

    dev_ids = TaskRegistry.list_task_ids(split="dev")
    assert len(dev_ids) == 14

    val_ids = TaskRegistry.list_task_ids(split="validation")
    assert len(val_ids) == 10

    test_ids = TaskRegistry.list_task_ids(split="test")
    assert len(test_ids) == 12


def test_fault_spec_aliases():
    f2 = FaultSpec.from_alias("F2")
    assert f2.boundary == ExecutionBoundary.POST_MUTATION_PRE_ACK
    assert f2.perturbation == Perturbation.ACK_LOSS
    assert f2.is_active is True

    f0 = FaultSpec.from_alias("F0")
    assert f0.boundary == ExecutionBoundary.PRE_MUTATION
    assert f0.perturbation == Perturbation.WORKER_CRASH

    nf = FaultSpec.from_alias("NO_FAULT")
    assert nf.boundary == ExecutionBoundary.NO_FAULT
    assert nf.is_active is False
