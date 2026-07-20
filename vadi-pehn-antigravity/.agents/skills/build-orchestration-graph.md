# Skill: Build/Extend Orchestration Graph

## Objective
As the Orchestration & Memory Engineer, extend the LangGraph turn pipeline
in `src/sibling/orchestration_graph.py` to cover the next capability in
scope (e.g. career-panel triggering, multi-turn context windowing) while
preserving the existing safety-gated control flow exactly.

## Rules of Engagement
- The existing node sequence — `check_input_safety` →
  (`handle_unsafe_input` | `retrieve_memory` → `generate_and_check_output`
  → `write_memory`) — is the spine. New capabilities are new nodes/edges
  added to this graph, not a parallel graph.
- Any new node that calls the LLM must sit downstream of
  `check_input_safety` returning `SAFE`, never upstream or in parallel.
- Any new node that produces user-facing text must have its output pass
  through `safety_client.check_output` before being included in
  `final_reply`.
- New state fields go in the `TurnState` TypedDict with a comment
  explaining what populates them and what consumes them.

## Instructions
1. Read the relevant System Design §5 sequence flow for the capability
   being added (e.g. §5.4 for panel-triggering).
2. Write the new node(s) as `async def` functions with the same signature
   pattern as existing nodes (`state: TurnState) -> TurnState`).
3. Wire them into `build_graph()` with `add_node`/`add_edge` or
   `add_conditional_edges`, matching the branching described in the System
   Design sequence flow.
4. Write or extend tests in `tests/test_orchestration_graph.py` covering:
   the new happy path, at least one safety-relevant edge case, and that
   pre-existing tests still pass.
5. Run the full test suite. Do not report the skill complete unless it's
   green — hand off to `@qa-auditor` via the `qa-loop` workflow if not.
6. If the new node reveals the System Design's sequence flow was
   incomplete or wrong, do not silently deviate — flag it to
   `@architect`/human via a note in your output, referencing the exact
   section.
