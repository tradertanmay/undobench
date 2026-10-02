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


class ProviderTransientError(Exception):
    """Raised when an LLM provider returns a transient error (e.g. 503, connection timeout) and retries are exhausted."""
    pass


class ProviderQuotaError(Exception):
    """Raised when an LLM provider returns rate limit / quota exhaustion (HTTP 429)."""
    pass


class ProviderAuthError(Exception):
    """Raised when an LLM provider authentication fails (HTTP 401/403)."""
    pass


def get_vertex_adc_token() -> Optional[str]:
    """Retrieves or refreshes Google Cloud Vertex AI ADC OAuth2 token."""
    token = os.environ.get("VERTEX_ACCESS_TOKEN")
    if token:
        return token
    try:
        adc_path = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
        if os.path.exists(adc_path):
            with open(adc_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if "refresh_token" in d:
                import urllib.parse
                import urllib.request
                data = urllib.parse.urlencode({
                    "client_id": d["client_id"],
                    "client_secret": d["client_secret"],
                    "refresh_token": d["refresh_token"],
                    "grant_type": "refresh_token",
                }).encode("utf-8")
                req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    return res.get("access_token")
    except Exception:
        pass
    return None


def resolve_llm_client_params(
    model_id: str,
    api_base: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Tuple[str, str, str]:
    """Resolves (canonical_model_id, base_url, api_key) with Vertex AI ADC support."""
    m_lower = model_id.lower()
    if "gemini" in m_lower or "glm" in m_lower or "zai-org" in m_lower or "vertex" in m_lower:
        gcp_project = os.environ.get("VERTEX_PROJECT_ID", "project-be311b86-00a5-4c33-9e5")
        gcp_location = os.environ.get("VERTEX_LOCATION", "global")
        default_base = f"https://aiplatform.googleapis.com/v1beta1/projects/{gcp_project}/locations/{gcp_location}/endpoints/openapi"

        # If passed api_base is default localhost, override with Vertex base
        resolved_base = api_base if (api_base and "localhost" not in api_base and "127.0.0.1" not in api_base) else default_base

        # Resolve ADC token
        resolved_key = api_key if (api_key and api_key != "ollama" and api_key != "dummy_key") else get_vertex_adc_token()
        if not resolved_key:
            resolved_key = os.environ.get("VERTEX_ACCESS_TOKEN", "dummy_token")

        # Canonical model name
        if "gemini" in m_lower:
            resolved_model = "google/gemini-3.8-flash" if "3.8" in m_lower else (model_id if model_id.startswith("google/") else f"google/{model_id}")
        elif "glm" in m_lower:
            resolved_model = "zai-org/glm-5.2-maas" if "5.2" in m_lower else (model_id if model_id.startswith("zai-org/") else f"zai-org/{model_id}")
        else:
            resolved_model = model_id

        return resolved_model, resolved_base, resolved_key
    else:
        # Default / Ollama / OpenAI
        resolved_base = api_base or os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
        resolved_key = api_key or os.environ.get("OPENAI_API_KEY", "ollama")
        return model_id, resolved_base, resolved_key


def call_llm_with_provider_retry(
    client: Any,
    create_kwargs: Dict[str, Any],
    max_retries: int = 5,
    initial_backoff: float = 1.0,
) -> Any:
    """Invokes chat completions API with exponential backoff on transient provider errors."""
    import time
    import random
    for attempt in range(max_retries + 1):
        try:
            return client.chat.completions.create(**create_kwargs)
        except Exception as e:
            err_str = str(e)
            status_code = getattr(e, "status_code", None)

            # Check for Auth error
            if status_code in (401, 403) or "unauthorized" in err_str.lower() or "authentication" in err_str.lower():
                if attempt == 0:
                    new_token = get_vertex_adc_token()
                    if new_token:
                        client.api_key = new_token
                        time.sleep(0.5)
                        continue
                raise ProviderAuthError(f"PROVIDER_AUTH_ERROR: {err_str}") from e

            # Check for Rate Limit / Quota
            is_rate_limit = status_code == 429 or "rate limit" in err_str.lower() or "quota" in err_str.lower() or "resource_exhausted" in err_str.lower()

            # Check for Transient Server / Network error
            is_server_error = (status_code and status_code >= 500) or any(
                phrase in err_str.lower() for phrase in [
                    "503", "502", "504", "500", "overloaded", "unavailable",
                    "connection refused", "connection reset", "broken pipe",
                    "remote disconnected", "timeout", "timed out", "apitimeouterror",
                    "apiconnectionerror"
                ]
            )

            if (is_rate_limit or is_server_error) and attempt < max_retries:
                backoff = initial_backoff * (2 ** attempt) + random.uniform(0.1, 0.5)
                time.sleep(backoff)
                continue

            if is_rate_limit:
                raise ProviderQuotaError(f"PROVIDER_QUOTA_EXCEEDED: {err_str}") from e
            elif is_server_error:
                raise ProviderTransientError(f"PROVIDER_TRANSIENT_FAILURE: {err_str}") from e
            else:
                raise e

