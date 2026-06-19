## Purpose
This document defines the operational rules and constraints for all LLM agents (Codex, Claude, etc.) working on this project.

All agents MUST follow these rules strictly.

---
## 0. Rule Priority

If rules conflict, follow this priority:

1. Assumption Compliance (Rule 1)
2. Structure Preservation (Rule 2)
3. Correctness (Debugging Rules)
4. Code Safety (Code Modification Rules)
5. Minimality

The agent MUST resolve conflicts according to this order.

---
## 1. Assumption Compliance Rule

- The agent MUST NOT violate `docs/assumptions.md`.

- If a change is required:
  1. The agent MUST explicitly request the change to the user.
  2. The agent MUST provide:
     - Original text
     - Modified text
  3. The agent MUST receive explicit user approval.
  4. Only after approval, the agent MAY update `docs/assumptions.md` and proceed.

---
## 2. Structure Preservation Rule

- The agent MUST NOT modify:
  - Project folder structure
  - File roles defined in `docs/architecture.md`

- If modification is needed:
  1. Provide:
     - Original structure text
     - Proposed structure text
     - Reason for change
  2. Get explicit user approval
  3. Update `docs/architecture.md`
  4. Append change log at the bottom of `docs/architecture.md`:

     - Date
     - Reason
     - User approval justification

---
## 3. Debugging Rules

- Do not guess the fix
- Identify root cause before patching
- Explain failure mechanism before modifying code

---
## 4. Hypothesis Tracking

All non-established mechanisms MUST be explicitly marked as:

- Hypothesis
- Experimental
- Unsupported

Do NOT present hypotheses as facts.

---
## 5. Code Modification Rules

1. Minimal Change Principle
   - Only change what is necessary

2. No Silent Refactor
   - Structural changes MUST be explicitly declared

3. Preserve Existing Behavior
   - Do not break working components

4. Add Before Replace
   - New implementations MUST NOT overwrite existing ones immediately

5. Testability
   - All changes MUST include at least one of the following:
     - A minimal runnable example
     - A test function
     - A clear verification procedure

   - The agent MUST explain how to verify correctness.

6. Replacement Condition
   - Always explicitly ask the user if the old implementation can be replaced.
   - Old implementation MAY be removed ONLY IF:
     1. New implementation is verified
     2. User explicitly approves removal

7. Code Documentation
   - All new or modified functions MUST include a docstring or inline comment explaining:
     - Purpose
     - Parameters (if non-obvious)
     - Return value (if non-obvious)
   - Hypothesis-tagged code MUST include a comment explaining the assumption being made.

---
## 6. Multi-Agent Coordination

Before modifying any file, the agent MUST:

1. Declare the target file(s)
2. Assume exclusive ownership during the task

Agents MUST NOT modify the same file concurrently.

Ownership is released when:
- Task is completed
- User explicitly cancels the task
- Agent declares failure

---
## 7. Document Scope Definition

- `docs/assumptions.md` defines:
  - Environment
  - Agent design constraints
  - Learning rules

- `docs/architecture.md` defines:
  - Folder hierarchy
  - File roles
  - Data flow

The agent MUST NOT reinterpret or extend these documents arbitrarily.

---
## Notes

- `docs/assumptions.md` and `docs/architecture.md` are referenced by this policy but are not initialized yet.
- Until those files exist, agents should treat them as reserved documents and ask before creating them.
