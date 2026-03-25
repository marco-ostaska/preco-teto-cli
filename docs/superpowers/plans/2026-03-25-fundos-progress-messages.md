# Fundos Progress Messages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `fundos-br` progress output distinguish download, cache hit, and processing phases for CVM quote ZIP files.

**Architecture:** Keep the existing cache and parsing flow intact. Return the ZIP source (`download` or `cache`) from the loader and emit explicit progress messages before load and before parse.

**Tech Stack:** Python, pytest, pandas

---

### Task 1: Add failing progress-message tests

**Files:**
- Modify: `tests/fundos/test_cotas.py`

- [ ] **Step 1: Write failing tests for download/cache/process messages**
- [ ] **Step 2: Run the focused test to verify it fails**
- [ ] **Step 3: Implement the minimal code**
- [ ] **Step 4: Run the focused test to verify it passes**

### Task 2: Verify no regressions

**Files:**
- Modify: `src/preco_teto/fundos/services/cotas.py`

- [ ] **Step 1: Run `uv run pytest tests/fundos/test_cotas.py -q`**
- [ ] **Step 2: Run `uv run pytest tests/ -q`**
