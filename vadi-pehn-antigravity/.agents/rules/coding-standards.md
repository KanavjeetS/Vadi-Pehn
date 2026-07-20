# Rule: Coding Standards

Applies to all Python code in this workspace.

- Python 3.10+, full type hints on public functions and dataclass fields.
- Format with `black`, lint with `ruff`. Run both before considering any
  change complete.
- Every module that talks to an external system (LLM, DB, HTTP) exposes an
  abstract base class plus at least one mock implementation, following the
  pattern in `src/sibling/llm_client.py` and `src/sibling/safety.py`.
- No bare `except:` clauses. Catch specific exceptions. On any safety or
  memory-isolation path, an unhandled exception must fail closed, not
  propagate as a generic 500 that might be swallowed upstream.
- Prefer `async def` for anything on the request path (matches the
  existing FastAPI + LangGraph async style in `api.py`).
- New environment variables get added to `config.py`'s `Settings`
  dataclass with a sensible mock-safe default — never read `os.environ`
  directly elsewhere in the codebase.
- Docstrings on every new module explain: what it's a production stand-in
  for (if a mock), which System Design/PRD section it implements, and what
  it deliberately does NOT do.
