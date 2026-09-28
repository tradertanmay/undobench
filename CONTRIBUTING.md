# Contributing to RecoverBench

Thank you for your interest in contributing to RecoverBench!

## 1. Scientific Immutability Policy (Important)

RecoverBench **v1.0.1** is a scientifically frozen benchmark:
- **Frozen TEST Tasks**: The 12 held-out TEST tasks, their parameter schemas, initial environment states, and state oracles are permanently locked.
- **Frozen Checksums**: Pull Requests that alter existing v1.0.1 task files or change the composite checksum (`TEST_SET_SHA256_V1_0_1.txt`) will fail CI.
- **Future Benchmark Versions**: Any modifications to task semantics, fault distributions, or evaluation rules must be proposed as a new minor or major benchmark version (e.g., v1.1.0).

## 2. Where Contributions Are Welcomed

We actively welcome contributions in the following areas:
- **New Agent Adapters**: Adding reference adapters for popular agent frameworks (AutoGPT, CrewAI, Semantic Kernel, etc.) in `examples/`.
- **CLI & SDK Ergonomics**: Improving developer tools, documentation, reporting formats, and export plugins.
- **New Task Proposals**: Developing candidate workflows for future benchmark splits in `recoverbench/tasks/dev/`.
- **Bug Fixes**: Resolving issues in sandbox mock behaviors or offline metric calculators that do not impact frozen TEST tasks.

## 3. Development Workflow

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/tradertanmay/recoverbench.git
   cd recoverbench
   ```
2. Create a clean virtual environment and install in editable mode with development dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e ".[all,dev]"
   ```
3. Run environment diagnostics and smoke tests:
   ```bash
   recoverbench doctor
   recoverbench smoke
   ```
4. Run the automated test suite:
   ```bash
   pytest tests/
   ```
5. Submit a Pull Request following conventional commits:
   - `feat(...)`: New feature or adapter
   - `fix(...)`: Bug fix
   - `docs(...)`: Documentation improvement
   - `test(...)`: Adding or improving tests
