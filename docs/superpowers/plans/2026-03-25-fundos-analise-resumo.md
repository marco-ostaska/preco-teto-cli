# Fundos Analise Resumo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mechanical fund summary, a R$ 100 12-month simulation, and percentage visibility in the 36-month consistency text for `fundos-br`.

**Architecture:** Keep the existing calculations and thermometers, then derive a lightweight summary from existing 12m performance, consistency, and alert data. Render the new summary block above the risk section and enrich the consistency suffix with a percentage.

**Tech Stack:** Python, Typer, Rich, pytest, pandas

---

### Task 1: Add failing tests for the summary rules

**Files:**
- Modify: `tests/fundos/test_termometro.py`
- Modify: `tests/fundos/test_cli.py`
- Create: `tests/fundos/test_tabela.py`

- [ ] **Step 1: Write failing tests for `analise_fundo`**
- [ ] **Step 2: Write failing tests for the rendered summary/simulation/consistency text**
- [ ] **Step 3: Run focused tests and verify they fail**

### Task 2: Implement minimal summary logic

**Files:**
- Modify: `src/preco_teto/fundos/termometro.py`
- Modify: `src/preco_teto/fundos/cli.py`
- Modify: `src/preco_teto/fundos/output/tabela.py`

- [ ] **Step 1: Add `analise_fundo` helper**
- [ ] **Step 2: Compute 12m simulation data in the CLI**
- [ ] **Step 3: Render summary block and consistency percentage**
- [ ] **Step 4: Run focused tests and verify they pass**

### Task 3: Verify no regressions

**Files:**
- Modify: existing files only

- [ ] **Step 1: Run `uv run pytest tests/fundos/test_termometro.py tests/fundos/test_cli.py tests/fundos/test_tabela.py -q`**
- [ ] **Step 2: Run `uv run pytest tests/ -q`**
