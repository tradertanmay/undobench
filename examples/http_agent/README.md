# HTTP Agent Adapter Example

This directory demonstrates how to evaluate non-Python agents (written in Go, Rust, TypeScript, Java, or C#) via HTTP REST.

## Running the Example

1. Start the Python mock HTTP server:
   ```bash
   python examples/http_agent/server.py --port 8080
   ```
2. In a separate terminal, evaluate the HTTP agent:
   ```bash
   recoverbench run --agent-url http://127.0.0.1:8080 --suite smoke
   ```
