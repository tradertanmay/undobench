# Changelog

All notable changes to RecoverBench are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-09-25 (Benchmark Freeze V1.0.1)

### Benchmark Protocol (Scientifically Frozen)
- **TEST Task Suite Freeze**: Cryptographically locked 12 held-out TEST tasks with composite SHA-256 `42ad17acaf97fcd480b8b152f8fbbc4df98acc54dfadd686c425b826dd69e0d8`.
- **Primary Trajectory Dataset**: Preserved frozen raw execution trajectories in `results/rb3c_test_raw.jsonl` with pre-registered SHA-256 digest `1016768449aae019484130b23fda33456861abeb161a5f8dfbeb16e9e5e9f882`.
- **Metric Formulation**: Formalized Conditional Recovery Success Rate (CRSR), conditioning recovery success strictly on nominal task competence ($C_i = 1$).
- **Safety Metrics**: Formalized Exactly-Once Rate (EOR), Duplicate Effect Rate (DER), Missing Effect Rate (MER), and Unsafe Retry Rate (URR).
- **Execution Boundaries**: Standardized five canonical fault injection boundaries (`PRE_MUTATION`, `DURING_MUTATION`, `POST_MUTATION_PRE_ACK`, `POST_ACK_PRE_CHECKPOINT`, `DURING_COMPENSATION`).

### SDK v1.0.0 Release Candidate
- **Unified CLI**: Introduced `recoverbench` CLI supporting `doctor`, `smoke`, `tasks`, `run`, `evaluate`, `report`, `inspect`, `submit`, and `version`.
- **Framework-Neutral Agent Protocol**: Standardized `RecoverBenchAgent` interface supporting Python scripts, HTTP microservices, LangGraph, and OpenAI-compatible endpoints.
- **Two-Tier Trust Model**: Standardized `OPEN_REPRODUCIBLE` local evaluation and `OFFICIAL_VERIFIED` hosted leaderboard evaluation pipelines.
- **Sandboxed Domain Tools**: Implemented 8 deterministic domain sandboxes (Cloud, CRM, Database, Git, Messaging, Payments, Storage, Ticketing).
