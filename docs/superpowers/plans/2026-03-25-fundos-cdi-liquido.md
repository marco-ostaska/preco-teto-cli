# Fundos CDI Liquido Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CDI liquido (15% fixed tax haircut) alongside CDI bruto in `fundos-br` output while keeping existing thermometers based on CDI bruto.

**Architecture:** Extend the fund-period calculation to produce both gross and net CDI benchmark values. Keep consistency and alert logic unchanged, and widen the renderer table with `CDI Líq.` and `% CDI Líq.` columns.

**Tech Stack:** Python, Typer, Rich, pytest, pandas

---

### Task 1: Add failing tests for net CDI comparison

**Files:**
- Modify: `tests/fundos/test_cli.py`
- Modify: `tests/fundos/test_formulas.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run the focused tests to verify they fail**
- [ ] **Step 3: Implement the minimal code**
- [ ] **Step 4: Run the focused tests to verify they pass**

### Task 2: Compute and render CDI liquido

**Files:**
- Modify: `src/preco_teto/fundos/formulas.py`
- Modify: `src/preco_teto/fundos/cli.py`
- Modify: `src/preco_teto/fundos/output/tabela.py`

- [ ] **Step 1: Add helper(s) for CDI liquido accumulation**
- [ ] **Step 2: Thread gross and net benchmark values through period output**
- [ ] **Step 3: Render the extra columns without changing gross-based thermometers**
- [ ] **Step 4: Run focused tests**

### Task 3: Verify full behavior

**Files:**
- Modify: `tests/fundos/test_cli.py`

- [ ] **Step 1: Run `uv run pytest tests/fundos/test_cli.py tests/fundos/test_formulas.py -q`**
- [ ] **Step 2: Run `uv run pytest tests/ -q`**
