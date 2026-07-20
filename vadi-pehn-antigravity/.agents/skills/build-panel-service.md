# Skill: Build Panel Service (CrewAI Discovery Panels)

## Objective
As the Orchestration & Memory Engineer, build the Panel Service per System
Design §4.4/§5.4: CrewAI-based multi-agent career discovery panels,
invoked as an async LangGraph tool call, never as the default 1:1 path.

## Rules of Engagement
- Panel composition selects top-2 interest matches PLUS one
  diversity-constraint persona (PRD §5.1) — implement the diversity
  constraint as a real, testable rule (e.g. "at least one persona is drawn
  from outside the learner's top-matched cluster, refreshed periodically"),
  not a comment saying it should exist.
- "Relationship Bandwidth" = max 3 concurrently introduced personas per
  learner (System Design §3.3's `introduced_relationships` table) — a 4th
  requires the lowest-engagement existing one to lapse first (45+ days
  inactive). Enforce this in the introduction-eligibility check, not just
  in a comment.
- If no clean taxonomy match exists for a learner's interests, do NOT
  force a mismatched panel — mark `no_match_fallback` and queue the
  interest for nightly curation review (PRD §5.2).
- The child must never face silence during panel composition — implement
  the immediate in-character acknowledgment from PRD §5.3 ("let me go ask
  my friends...") as part of the Orchestration Service's response, before
  the panel result is ready.

## Instructions
1. Implement `POST /internal/v1/panel/compose` and
   `GET /internal/v1/panel/{panel_id}/status` exactly per System Design
   §4.4's contract.
2. Implement panel selection against `professional_personas` and
   `learner_interest_profile` (System Design §3.3 schema).
3. Implement the CrewAI crew: 3 personas deliberating on the learner's
   question, with output validated against
   `professional_personas.approved_fact_source_ref` before being returned
   (Output Guard, PRD's hallucination-mitigation requirement).
4. Add a LangGraph tool node in `orchestration_graph.py` that triggers
   panel composition on detected broad-career-question intent, per System
   Design §5.4's sequence — this is an extension task, use the
   `build-orchestration-graph.md` skill's rules for how to add it safely.
5. Write unit tests for: correct top-2 + diversity selection, bandwidth
   enforcement blocking a 4th active introduction, and the no-match
   fallback path.
