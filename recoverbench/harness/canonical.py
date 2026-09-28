"""RecoverBench Canonical Contracts, Tool Schemas, and Return Envelope Normalization."""

from __future__ import annotations
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from recoverbench.schemas.task import TaskSpec


def _resolve_asset_path(filename: str) -> str:
    # 1. Check packaged data directory inside recoverbench/data/
    pkg_data = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", filename)
    if os.path.exists(pkg_data):
        return pkg_data
    # 2. Check current working directory
    if os.path.exists(filename):
        return filename
    # 3. Check workspace root
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root_path = os.path.join(base_dir, filename)
    if os.path.exists(root_path):
        return root_path
    return pkg_data


def load_canonical_system_prompt(version: str = "V4") -> str:
    path = _resolve_asset_path(f"SYSTEM_PROMPT_{version}.txt")
    if not os.path.exists(path):
        path = path.replace("V4", "V3").replace("V3", "V2").replace("V2", "V1")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_canonical_tool_schemas(version: str = "V4") -> Dict[str, Any]:
    path = _resolve_asset_path(f"CANONICAL_TOOL_SCHEMAS_{version}.json")
    if not os.path.exists(path):
        path = path.replace("V4", "V3").replace("V3", "V2").replace("V2", "V1")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["tools"]


def load_task_prompt_template(version: str = "V4") -> str:
    path = _resolve_asset_path(f"TASK_PROMPT_TEMPLATE_{version}.txt")
    if not os.path.exists(path):
        path = path.replace("V4", "V3").replace("V3", "V2").replace("V2", "V1")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def format_user_prompt(task: TaskSpec, version: str = "V4") -> str:
    """Generate the user prompt strictly from the public task description."""
    template = load_task_prompt_template(version=version)
    return template.format(
        task_id=task.task_id,
        objective=task.objective,
    )


def get_openai_tools(allowed_tools: List[str], version: str = "V4") -> List[Dict[str, Any]]:
    """Generate OpenAI-standard function tool definitions for allowed tools."""
    all_schemas = load_canonical_tool_schemas(version=version)
    tools = []
    missing_tools = []
    for tool_name in allowed_tools:
        if tool_name in all_schemas:
            spec = all_schemas[tool_name]
            tools.append({
                "type": "function",
                "function": {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters": spec["parameters"],
                }
            })
        else:
            missing_tools.append(tool_name)
    if missing_tools:
        raise KeyError(
            f"Harness Schema Omission: Allowed tools {missing_tools} missing from canonical schemas ({version})."
        )
    return tools


def coerce_tool_arguments(fn_name: str, args: Dict[str, Any], schemas: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Generic schema-driven type coercion for tool calling interfaces.
    
    Prevents Python runtime TypeErrors when LLMs serialize numeric or boolean values as strings.
    """
    if schemas is None:
        schemas = load_canonical_tool_schemas(version="V4")

    tool_def = schemas.get(fn_name)
    if not tool_def:
        return args

    properties = tool_def.get("parameters", {}).get("properties", {})
    required_keys = set(tool_def.get("parameters", {}).get("required", []))
    coerced = dict(args)

    # Specific signature compatibility guard for complete_multipart_upload
    if fn_name == "complete_multipart_upload" and "parts" not in coerced:
        coerced["parts"] = []

    for param_name, param_spec in properties.items():
        if param_name not in coerced:
            continue

        expected_type = param_spec.get("type")
        val = coerced[param_name]

        # Generic number coercion
        if expected_type == "number" and isinstance(val, str):
            try:
                coerced[param_name] = float(val)
            except ValueError:
                pass
        # Generic integer coercion
        elif expected_type == "integer":
            if isinstance(val, str):
                try:
                    coerced[param_name] = int(val)
                except ValueError:
                    pass
            elif isinstance(val, float) and val.is_integer():
                coerced[param_name] = int(val)
        # Generic boolean coercion
        elif expected_type == "boolean" and isinstance(val, str):
            if val.lower() == "true":
                coerced[param_name] = True
            elif val.lower() == "false":
                coerced[param_name] = False
        # Remove empty string arguments for optional omitted parameters
        elif param_name not in required_keys and val == "":
            del coerced[param_name]

    return coerced


def format_return_envelope(result: Any = None, error: Optional[Exception] = None) -> Dict[str, Any]:
    """Normalize tool return values into canonical envelope, masking internal benchmark faults."""
    if error is not None:
        err_type = type(error).__name__
        err_msg = str(error)

        # Fault transparency rule: mask internal benchmark artifacts behind realistic transport errors
        if "AckLoss" in err_type or "Lost ACK" in err_msg:
            clean_message = "ConnectionResetError: Connection reset by peer while waiting for server response."
        elif "Timeout" in err_type or "timed out" in err_msg.lower():
            clean_message = "TimeoutError: Request timed out before response was received."
        elif "WorkerCrash" in err_type or "Worker crashed" in err_msg:
            clean_message = "RuntimeError: Remote worker process terminated unexpectedly."
        elif "RecoveryFailure" in err_type or "Recovery crashed" in err_msg:
            clean_message = "RuntimeError: Remote service encountered an internal failure during transaction processing."
        elif "PartialWrite" in err_type:
            clean_message = "IOError: Broken pipe / partial write during stream transmission."
        else:
            # Strip internal benchmark prefixes if any
            clean_message = re.sub(r"\[RECOVERBENCH INJECTED\]\s*", "", err_msg)
            clean_message = f"{err_type}: {clean_message}"

        return {
            "status": "error",
            "result": {},
            "message": clean_message,
        }

    return {
        "status": "success",
        "result": result if result is not None else {},
        "message": "Operation completed successfully.",
    }
