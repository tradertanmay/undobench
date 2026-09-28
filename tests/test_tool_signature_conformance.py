"""Automated Conformance Tests for RecoverBench Tool Schemas and Signatures."""

import inspect
import pytest
from recoverbench.harness.canonical import (
    coerce_tool_arguments,
    format_return_envelope,
    get_openai_tools,
    load_canonical_tool_schemas,
)
from recoverbench.tasks.registry import TaskRegistry, TASK_FACTORIES


def test_all_36_tasks_have_complete_canonical_schemas():
    """Verify that 100% of tasks across DEV, VALIDATION, and TEST have all allowed tools in V4 schemas."""
    schemas = load_canonical_tool_schemas(version="V4")
    assert len(TASK_FACTORIES) == 36, f"Expected 36 tasks, found {len(TASK_FACTORIES)}"

    missing_by_task = {}
    for task_id in sorted(TASK_FACTORIES.keys()):
        task_spec, _, _ = TaskRegistry.load_task(task_id)
        missing = [t for t in task_spec.allowed_tools if t not in schemas]
        if missing:
            missing_by_task[task_id] = missing

    assert not missing_by_task, f"Tasks with missing tool schemas in V4: {missing_by_task}"


def test_schema_parameters_match_callable_signatures():
    """Verify that every parameter required by sandbox callables is present in V4 schemas."""
    schemas = load_canonical_tool_schemas(version="V4")

    for task_id in sorted(TASK_FACTORIES.keys()):
        task_spec, _, proxy_reg = TaskRegistry.load_task(task_id)
        for tool_name in task_spec.allowed_tools:
            assert tool_name in schemas, f"Tool '{tool_name}' for task '{task_id}' missing in schemas"
            schema_def = schemas[tool_name]
            schema_props = schema_def["parameters"]["properties"]

            fn = proxy_reg._raw_tools.get(tool_name)
            assert fn is not None, f"Tool '{tool_name}' missing in proxy registry for '{task_id}'"

            sig = inspect.signature(fn)
            py_req = [p.name for p in sig.parameters.values() if p.default == inspect.Parameter.empty]

            for param in py_req:
                assert param in schema_props, (
                    f"Required parameter '{param}' of '{tool_name}' in task '{task_id}' missing from schema properties!"
                )


def test_complete_multipart_upload_signature_and_coercion():
    """Verify that complete_multipart_upload schema includes parts and coerces properly."""
    schemas = load_canonical_tool_schemas(version="V4")
    tool_def = schemas["complete_multipart_upload"]
    assert "parts" in tool_def["parameters"]["properties"]
    assert tool_def["parameters"]["properties"]["parts"]["type"] == "array"

    # Test coercion when LLM omits parts
    coerced = coerce_tool_arguments("complete_multipart_upload", {"upload_id": "test_up_123"}, schemas=schemas)
    assert "parts" in coerced
    assert coerced["parts"] == []
    assert coerced["upload_id"] == "test_up_123"

    # Test coercion when LLM provides parts
    explicit_parts = [{"part_number": 1, "etag": "abc"}]
    coerced_explicit = coerce_tool_arguments("complete_multipart_upload", {"upload_id": "test_up_123", "parts": explicit_parts}, schemas=schemas)
    assert coerced_explicit["parts"] == explicit_parts


def test_format_return_envelope_normalization():
    """Verify standard return envelope structure for success and masked errors."""
    success_env = format_return_envelope({"data": 42})
    assert success_env["status"] == "success"
    assert success_env["result"] == {"data": 42}
    assert "message" in success_env

    err_env = format_return_envelope(error=ConnectionResetError("Connection lost"))
    assert err_env["status"] == "error"
    assert err_env["result"] == {}
    assert "ConnectionResetError" in err_env["message"]


def test_get_openai_tools_raises_on_missing_tool():
    """Verify that get_openai_tools fails fast on missing tools instead of dropping them."""
    with pytest.raises(KeyError) as exc_info:
        get_openai_tools(["non_existent_tool_xyz"], version="V4")
    assert "Harness Schema Omission" in str(exc_info.value)
