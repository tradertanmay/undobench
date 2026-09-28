# Security Policy

## 1. Supported Versions

| Version | Supported |
| :--- | :--- |
| `1.0.x` | :white_check_mark: |
| `< 1.0.0` | :x: |

## 2. Reporting a Vulnerability

If you discover a security vulnerability in RecoverBench, please do **NOT** open a public issue.
Instead, report the issue via GitHub Private Vulnerability Reporting or contact:
`security@recoverbench.org`

Please include:
- A description of the vulnerability and attack vector.
- Steps or a minimal script to reproduce the issue.
- Impact on evaluated agent environments or host systems.

We commit to acknowledging receipt within 48 hours and providing a remediation timeline within 7 business days.

## 3. Sandbox Security Model

RecoverBench evaluates AI agents by instantiating simulated, local domain environments (e.g. SQLite databases, mock cloud routes, in-memory payment ledger).
- All standard sandboxes run in process-isolated or memory-backed modes.
- RecoverBench does not invoke real cloud credentials, external banking APIs, or live production infrastructure during standard runs.
- However, when running untrusted custom agent code, researchers should execute RecoverBench within containerized boundaries (e.g. using the provided `Dockerfile`).
