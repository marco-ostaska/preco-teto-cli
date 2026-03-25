# Fundos Benchmark Explicito Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `--benchmark` flow to `fundos-br` and make `CDI`, `DIVO11`, `IVV`, `BTC`, and `USD` real benchmarks with matching calculations and output.

**Architecture:** Move benchmark selection into the CLI boundary, then centralize historical series loading in the benchmark service. Keep `CDI`-specific features isolated so the CLI can render a richer table for `CDI` and a generic comparison layout for non-`CDI` benchmarks while reusing the same performance, consistency, and alert flow.

**Tech Stack:** Python, Typer, Rich, pandas, requests, yfinance, pytest

---

### Task 1: Add failing tests for benchmark selection

**Files:**
- Modify: `tests/fundos/test_benchmark.py`
- Modify: `tests/fundos/test_cli.py`

- [ ] **Step 1: Add tests for supported benchmark validation and series loading entry points**
- [ ] **Step 2: Add CLI tests for `--benchmark` bypassing prompts**
- [ ] **Step 3: Add CLI tests for interactive prompt when `--benchmark` is absent**
- [ ] **Step 4: Run focused tests and verify they fail**

### Task 2: Implement benchmark service support

**Files:**
- Modify: `src/preco_teto/fundos/services/benchmark.py`
- Modify: `tests/fundos/test_benchmark.py`

- [ ] **Step 1: Add supported benchmark constants and input normalization**
- [ ] **Step 2: Add historical fetchers for market benchmarks and `USD`**
- [ ] **Step 3: Add a unified helper to load the selected benchmark series**
- [ ] **Step 4: Run benchmark tests and verify they pass**

### Task 3: Wire explicit benchmark flow through the CLI

**Files:**
- Modify: `src/preco_teto/fundos/cli.py`
- Modify: `tests/fundos/test_cli.py`

- [ ] **Step 1: Add `--benchmark` option and prompt fallback**
- [ ] **Step 2: Replace `CDI`-only period calculations with generic benchmark calculations**
- [ ] **Step 3: Make consistency and alert use the selected benchmark series**
- [ ] **Step 4: Run CLI tests and verify they pass**

### Task 4: Render `CDI` and non-`CDI` outputs correctly

**Files:**
- Modify: `src/preco_teto/fundos/output/tabela.py`
- Modify: `tests/fundos/test_tabela.py`

- [ ] **Step 1: Add rendering coverage for non-`CDI` tables and simulation text**
- [ ] **Step 2: Keep `CDI` liquid columns and hide them for other benchmarks**
- [ ] **Step 3: Run table tests and verify they pass**

### Task 5: Verify the whole feature

**Files:**
- Modify: existing files only

- [ ] **Step 1: Run `uv run pytest tests/fundos/test_benchmark.py tests/fundos/test_cli.py tests/fundos/test_tabela.py -q`**
- [ ] **Step 2: Run `uv run pytest tests/ -q`**
