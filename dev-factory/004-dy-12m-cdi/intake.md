# Intake

## Slug & branch

- Slug: `004-dy-12m-cdi`
- Branch: `feat/espacamento-resultado`
- This is a new story folder because the existing numbered folders cover different stories through `003`.

## Problem

For FIIs, show the dividend yield accumulated over the last 12 months and add a separate ceiling price that compares that yield directly with CDI. Keep the existing ceiling based on `melhor_indice`; the new comparison must use CDI specifically.

## Codebase explored

- `src/preco_teto/services/fii.py:61-105` parses the current site DY and the available dividend history; `:121-156` exposes dividend properties; `:194-255` builds `FiiData`.
- `src/preco_teto/cli.py:99-125` calculates FII ceilings using `melhor_indice` and passes FII metrics to the renderer.
- `src/preco_teto/formulas.py:54-65` provides `teto_por_dy(dividendo_anual, indice_base)`.
- `src/preco_teto/output/tabela.py:108-127`, `plain.py:57-76`, and `json_out.py:29-41` render FII ceilings and dividend information.
- `tests/test_fii.py:108-209` covers the FII dividend parser and fallback behavior; `tests/test_cli_main.py:63-92` covers FII ceiling assembly.

## Project norms & constraints

- Test framework: pytest, with fixtures and mocks in `tests/conftest.py:62-199`; the active FII test file is `tests/test_fii.py`.
- Baseline `uv run rtk pytest tests/ -v`: 165 passed, 1 failed in the unrelated `tests/fundos/test_cadastro.py::test_buscar_fundo_prefere_registro_ativo_no_cadastro_legado` test.
- Existing worktree changes are present in unrelated product files and must not be reverted.
- No disabled/commented-out test suite was found in the inspected FII tests. Existing scraper parsing and yfinance fallback are red flags for data availability and must preserve `None` when 12 months are unavailable.
- Tooling uses Python, uv, pytest, pandas, BeautifulSoup, and yfinance.

## Decisions made

- Compute 12-month DY from the sum of the latest 12 parsed monthly distributions divided by the current price, expressed as a percentage.
- Expose the 12-month DY as FII data and show it in table, plain, and JSON output.
- Add a distinct FII ceiling using the 12-month annual distribution and `indices.cdi`; leave the existing `melhor_indice` ceilings unchanged.
- Return no 12-month DY or CDI ceiling when fewer than 12 distributions or required values are available.

## What was rejected

- Replacing the existing `melhor_indice` calculation with CDI was rejected because the user explicitly requested an additional comparison, not a replacement.
- Reusing the site's displayed DY was rejected because the requested metric is explicitly the last 12 months.

## Work chunks identified

- Add FII 12-month DY calculation and data field.
- Add CDI-based ceiling and render it in all output formats.
- Extend existing tests and run focused/full verification.

## Next steps

Write failing tests in the existing FII and CLI test files, implement the smallest compatible changes, then run focused tests and the full suite while documenting the unrelated baseline failure if it remains.
