# Codex Interactive Questions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document Codex-specific interactive-question behavior in every ai-footprint skill that asks for user input.

**Architecture:** This is a documentation-only consistency change. Each skill keeps its existing runtime-specific entries and generic textual fallback; a single Codex entry directs the agent to use `request_user_input` only when the runtime exposes it.

**Tech Stack:** Markdown skill instructions; `rg` for verification.

## Global Constraints

- Change all user-input skills together: report, card, resolve, and config.
- Never claim `request_user_input` is always available.
- Keep the current numbered-text fallback intact.
- Do not modify the ai-footprint CLI or generated reports.

---

### Task 1: Add Codex question handling to all input skills

**Files:**
- Modify: `skills/footprint-report/SKILL.md:57-61`
- Modify: `skills/footprint-card/SKILL.md:49-53`
- Modify: `skills/footprint-resolve/SKILL.md:61-65`
- Modify: `skills/footprint-config/SKILL.md:39-43`

**Interfaces:**
- Consumes: A Codex runtime that may or may not expose `request_user_input`.
- Produces: A uniform instruction to prefer structured interactive input and otherwise use each skill’s existing text fallback.

- [ ] **Step 1: Verify the current baseline**

Run:

```bash
rg -L 'request_user_input' skills/footprint-{report,card,resolve,config}/SKILL.md
```

Expected: the four skill paths are listed.

- [ ] **Step 2: Add the Codex runtime entry**

Insert immediately after each Claude Code bullet:

```md
- **Codex** : utiliser `request_user_input` si l’outil est exposé par le runtime ; sinon, utiliser le repli texte numéroté ci-dessous et attendre la réponse avant de poursuivre.
```

- [ ] **Step 3: Verify all skills and their fallbacks**

Run:

```bash
rg -n 'Codex.*request_user_input|Sinon.*(numérot|liste des mappings)' skills/footprint-{report,card,resolve,config}/SKILL.md
```

Expected: one Codex entry and one textual-fallback match in every skill.

- [ ] **Step 4: Commit**

```bash
git add skills/footprint-{report,card,resolve,config}/SKILL.md .superpowers/specs/2026-07-18-codex-questions-design.md .superpowers/plans/2026-07-18-codex-questions.md
git commit -m "docs(skills): document Codex interactive questions"
```
