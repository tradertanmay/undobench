"""Example 6: Standalone HTTP Agent Server for Mode C Evaluation.

A zero-dependency HTTP server implementing the RecoverBench HTTP Agent Protocol.
Demonstrates how agents written in Go, Rust, TypeScript, or other languages
can evaluate against RecoverBench over standard HTTP JSON.

Usage:
    # 1. Start the HTTP Agent in background or separate shell:
    python examples/http_agent/server.py --port 8080 &

    # 2. Benchmark the agent via RecoverBench CLI:
    recoverbench run --agent-url http://localhost:8080 --suite smoke
"""

from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
from typing import Any, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recoverbench.http_agent_server")


class RecoverBenchAgentHTTPHandler(BaseHTTPRequestHandler):
    """Handler implementing RecoverBench HTTP Agent REST protocol."""

    # Active session state: session_id -> step_index
    sessions: Dict[str, int] = {}

    def _send_json_response(self, status_code: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")

        try:
            payload = json.loads(post_data) if post_data else {}
        except Exception:
            self._send_json_response(400, {"error": "Invalid JSON"})
            return

        path = self.path.split("?")[0]

        if path == "/v1/agent/run":
            session_id = payload.get("session_id", "default_session")
            task = payload.get("task", {})
            task_id = task.get("task_id", "unknown")
            allowed_tools = payload.get("allowed_tools", [])

            self.sessions[session_id] = 0

            # If task has allowed tools, request invocation of first tool
            if allowed_tools:
                tname = allowed_tools[0]
                resp = {
                    "action": "call_tool",
                    "session_id": session_id,
                    "tool_name": tname,
                    "arguments": {},
                }
            else:
                resp = {
                    "action": "complete",
                    "session_id": session_id,
                    "status": "SUCCESS",
                    "final_message": f"Task {task_id} completed (no tools needed)",
                }
            self._send_json_response(200, resp)

        elif path == "/v1/agent/step":
            session_id = payload.get("session_id", "default_session")
            step_idx = self.sessions.get(session_id, 0) + 1
            self.sessions[session_id] = step_idx

            tool_name = payload.get("tool_name")
            tool_result = payload.get("result")

            # In this demo agent, after 1 step we complete
            resp = {
                "action": "complete",
                "session_id": session_id,
                "status": "SUCCESS",
                "final_message": f"Successfully processed tool '{tool_name}' result: {tool_result}",
                "llm_calls_count": 1,
            }
            self._send_json_response(200, resp)

        else:
            self._send_json_response(404, {"error": f"Endpoint {path} not found"})

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy standard request logging during benchmark runs
        pass


def run_server(port: int = 8080) -> None:
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, RecoverBenchAgentHTTPHandler)
    print(f"RecoverBench HTTP Agent Server running on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down HTTP agent server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    args = parser.parse_args()
    run_server(port=args.port)
