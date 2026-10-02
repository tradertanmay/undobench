"""Task Registry for RecoverBench Phase RB-2 (All 36 Tasks)."""

from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional, Tuple
from recoverbench.faults.proxy import ToolProxyRegistry
from recoverbench.schemas.task import TaskSpec

# DEV Tasks (14)
from recoverbench.tasks.dev.rb_cloud_002 import create_task_rb_cloud_002
from recoverbench.tasks.dev.rb_cloud_003 import create_task_rb_cloud_003
from recoverbench.tasks.dev.rb_crm_002 import create_task_rb_crm_002
from recoverbench.tasks.dev.rb_crm_003 import create_task_rb_crm_003
from recoverbench.tasks.dev.rb_db_001 import create_task_rb_db_001
from recoverbench.tasks.dev.rb_db_003 import create_task_rb_db_003
from recoverbench.tasks.dev.rb_git_001 import create_task_rb_git_001
from recoverbench.tasks.dev.rb_git_003 import create_task_rb_git_003
from recoverbench.tasks.dev.rb_msg_001 import create_task_rb_msg_001
from recoverbench.tasks.dev.rb_msg_003 import create_task_rb_msg_003
from recoverbench.tasks.dev.rb_pay_002 import create_task_rb_pay_002
from recoverbench.tasks.dev.rb_pay_003 import create_task_rb_pay_003
from recoverbench.tasks.dev.rb_stor_001 import create_task_rb_stor_001
from recoverbench.tasks.dev.rb_tick_002 import create_task_rb_tick_002

# VALIDATION Tasks (10)
from recoverbench.tasks.validation.rb_cloud_001 import create_task_rb_cloud_001
from recoverbench.tasks.validation.rb_crm_001 import create_task_rb_crm_001
from recoverbench.tasks.validation.rb_db_002 import create_task_rb_db_002
from recoverbench.tasks.validation.rb_git_002 import create_task_rb_git_002
from recoverbench.tasks.validation.rb_msg_002 import create_task_rb_msg_002
from recoverbench.tasks.validation.rb_pay_001 import create_task_rb_pay_001
from recoverbench.tasks.validation.rb_stor_002 import create_task_rb_stor_002
from recoverbench.tasks.validation.rb_stor_003 import create_task_rb_stor_003
from recoverbench.tasks.validation.rb_tick_001 import create_task_rb_tick_001
from recoverbench.tasks.validation.rb_tick_003 import create_task_rb_tick_003

# TEST Tasks (12 - Frozen Quarantine)
from recoverbench.tasks.test.rb_cloud_004 import create_task_rb_cloud_004
from recoverbench.tasks.test.rb_crm_004 import create_task_rb_crm_004
from recoverbench.tasks.test.rb_db_004 import create_task_rb_db_004
from recoverbench.tasks.test.rb_db_005 import create_task_rb_db_005
from recoverbench.tasks.test.rb_git_004 import create_task_rb_git_004
from recoverbench.tasks.test.rb_msg_004 import create_task_rb_msg_004
from recoverbench.tasks.test.rb_msg_005 import create_task_rb_msg_005
from recoverbench.tasks.test.rb_pay_004 import create_task_rb_pay_004
from recoverbench.tasks.test.rb_pay_005 import create_task_rb_pay_005
from recoverbench.tasks.test.rb_stor_004 import create_task_rb_stor_004
from recoverbench.tasks.test.rb_stor_005 import create_task_rb_stor_005
from recoverbench.tasks.test.rb_tick_004 import create_task_rb_tick_004

TASK_FACTORIES: Dict[str, Callable[[], Tuple[TaskSpec, Any, ToolProxyRegistry]]] = {
    # 14 DEV Tasks
    "RB-DB-001": create_task_rb_db_001,
    "RB-DB-003": create_task_rb_db_003,
    "RB-PAY-002": create_task_rb_pay_002,
    "RB-PAY-003": create_task_rb_pay_003,
    "RB-GIT-001": create_task_rb_git_001,
    "RB-GIT-003": create_task_rb_git_003,
    "RB-TICK-002": create_task_rb_tick_002,
    "RB-CLOUD-002": create_task_rb_cloud_002,
    "RB-CLOUD-003": create_task_rb_cloud_003,
    "RB-CRM-002": create_task_rb_crm_002,
    "RB-CRM-003": create_task_rb_crm_003,
    "RB-MSG-001": create_task_rb_msg_001,
    "RB-MSG-003": create_task_rb_msg_003,
    "RB-STOR-001": create_task_rb_stor_001,

    # 10 VALIDATION Tasks
    "RB-DB-002": create_task_rb_db_002,
    "RB-PAY-001": create_task_rb_pay_001,
    "RB-GIT-002": create_task_rb_git_002,
    "RB-TICK-001": create_task_rb_tick_001,
    "RB-TICK-003": create_task_rb_tick_003,
    "RB-CLOUD-001": create_task_rb_cloud_001,
    "RB-CRM-001": create_task_rb_crm_001,
    "RB-MSG-002": create_task_rb_msg_002,
    "RB-STOR-002": create_task_rb_stor_002,
    "RB-STOR-003": create_task_rb_stor_003,

    # 12 TEST Tasks (Frozen)
    "RB-DB-004": create_task_rb_db_004,
    "RB-DB-005": create_task_rb_db_005,
    "RB-PAY-004": create_task_rb_pay_004,
    "RB-PAY-005": create_task_rb_pay_005,
    "RB-GIT-004": create_task_rb_git_004,
    "RB-TICK-004": create_task_rb_tick_004,
    "RB-CLOUD-004": create_task_rb_cloud_004,
    "RB-CRM-004": create_task_rb_crm_004,
    "RB-MSG-004": create_task_rb_msg_004,
    "RB-MSG-005": create_task_rb_msg_005,
    "RB-STOR-004": create_task_rb_stor_004,
    "RB-STOR-005": create_task_rb_stor_005,
}


class TaskRegistry:
    """Registry providing clean initialization of benchmark tasks and sandboxes."""

    @classmethod
    def list_task_ids(cls, split: Optional[str] = None) -> List[str]:
        if not split:
            return list(TASK_FACTORIES.keys())
        res = []
        for tid, factory in TASK_FACTORIES.items():
            spec, _, _ = factory()
            if spec.split.value.lower() == split.lower():
                res.append(tid)
        return res

    @classmethod
    def get_task_spec(cls, task_id: str) -> TaskSpec:
        spec, _, _ = cls.load_task(task_id)
        return spec

    @classmethod
    def load_task(cls, task_id: str) -> Tuple[TaskSpec, Any, ToolProxyRegistry]:
        """Instantiate fresh task specification, sandbox, and tool proxy registry."""
        normalized_id = task_id.upper()
        if normalized_id not in TASK_FACTORIES:
            raise KeyError(f"Task '{task_id}' not found in registry. Available: {list(TASK_FACTORIES.keys())}")
        return TASK_FACTORIES[normalized_id]()
