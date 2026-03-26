# Contributing to RiskMesh

Thanks for your interest in contributing to RiskMesh! This guide will help you get started.

## Development Setup

1. **Fork and clone** the repository:

   ```bash
   git clone https://github.com/<your-username>/riskmesh.git
   cd riskmesh
   ```

2. **Create a virtual environment** and install in editable mode:

   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   venv\Scripts\activate      # Windows
   pip install -e ".[dev]"
   ```

3. **Run the tests** to make sure everything works:

   ```bash
   python -m pytest tests/ -v
   ```

4. **Start the server** to explore locally:

   ```bash
   python -m src.main
   ```

## Making Changes

1. Create a feature branch from `main`:

   ```bash
   git checkout -b feature/my-improvement
   ```

2. Make your changes. Keep commits small and focused.

3. Add or update tests for any new functionality.

4. Run the full test suite before pushing:

   ```bash
   python -m pytest tests/ -v
   ```

5. Push your branch and open a Pull Request against `main`.

## Pull Request Guidelines

- Write a clear title and description explaining **what** and **why**.
- Reference any related issues (e.g., `Fixes #42`).
- All tests must pass in CI before merging.
- Keep PRs focused: one feature or fix per PR.

## Code Style

- Use type hints on all public function signatures.
- Add docstrings to modules, classes, and public functions.
- Follow existing patterns in the codebase.

## Reporting Issues

Open an issue on GitHub with:
- A clear description of the problem or feature request.
- Steps to reproduce (for bugs).
- Expected vs. actual behavior.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
