# M0 Recon and Guards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the machine-checkable part of M0: know the data and the engine, put the test-day lock in place before any download code, and benchmark one day.

**Architecture:** A uv project with a `src/toxic_flow` package. The split lock is a small module that every downloader call goes through. Recon, download and conversion are scripts that write only to `data/` and `docs/`. The fixed-spread loop is a numba function driven by hftbacktest.

**Tech Stack:** Python 3.12, uv, hftbacktest 2.4.4, numba, numpy, polars, pyarrow, scipy, pyyaml, pytest, ruff, make.

**Spec:** SPEC.md section M0, SESSION_1.md, PREREGISTRATION.md sections 2 and 3, CLAUDE.md.

## Global Constraints

- Python 3.12. hftbacktest pinned to the newest release at least two weeks old.
- Never create, move or delete git tags. Never load or GET test-day data before prereg-v1.
- Do not edit scripts/check_milestone.py or configs/splits.yaml.
- data/raw is immutable and written only by the downloader, which never overwrites.
- No invented numbers about data, venue specs or fees. Unknowns become [TBD: question].
- No em dashes and no word from tests/writing_rules.txt in any .md or paper file.
- Polars and Parquet for tabular data. Use hftbacktest for simulation, no custom matcher.
- make check must pass before every commit; the pre-commit hook enforces it.

## Facts established during planning (2026-10-22)

- hftbacktest releases on PyPI: newest is 2.4.4, uploaded 2025-12-10, with a cp312
  macOS arm64 wheel. It is far more than two weeks old and nothing newer exists, so it is
  the pin. It needs numpy >=2.0,<2.3 and numba ~=0.61.
- `datasets.tardis.dev` answers HTTP HEAD with 404 for every URL, including files that a
  GET serves with 200 (checked on 2024-01-01 trades and incremental_book_L2, and on a
  nonexistent symbol). A GET on 2024-01-01 returns 200 with Content-Length
  546329028 (L2) and 20848659 (trades). Range requests are blocked by Cloudflare.
  Consequence: a HEAD-only recon cannot show HTTP 200 for any file, so AC0.1 cannot pass
  without a GET of test-day files, which this session forbids. This is open question Q1.
- The Tardis exchange API lists BTCUSDT with incremental_book_L2 and trades from
  2019-11-17 to 2026-10-22, and 18 incident reports, none on a split date.
- Machine: Apple M1 Pro, 8 cores (6 performance, 2 efficiency), 16 GiB RAM, 12 GiB free
  disk. The disk budget matters for M1 (18 days of raw plus converted data).

## Review Focus

1. A test date that is also passed as a raw string with a different format (for example
   `2025-07-01T00:00`) must still be refused. Task 3 normalises with `date.fromisoformat`.
2. The remote is unreachable or `origin` is missing: the lock must refuse, not allow.
   Task 3 has a test.
3. A local tag that differs from the remote tag (re-created after pushing) must be
   refused. Task 3 has a test.
4. The downloader is run twice: it must not rewrite a raw file, and must fail if the hash
   on disk no longer matches the manifest. Task 6 has a test.
5. A .md file inside `.venv/` or another ignored folder must not be linted, but an
   untracked new .md file must be. Task 2 lists files with
   `git ls-files --cached --others --exclude-standard`.

---

### Task 1: uv project, Makefile, pre-commit hook

**Files:**
- Create: `pyproject.toml`, `.python-version`, `uv.lock`, `Makefile`,
  `src/toxic_flow/__init__.py`, `src/toxic_flow/data/__init__.py`

- [ ] **Step 1:** `uv init --lib --name toxic-flow` equivalent by hand: package
  `toxic_flow` in `src/`, `requires-python = ">=3.12,<3.13"`, `.python-version` 3.12.
- [ ] **Step 2:** `uv add hftbacktest==2.4.4 polars pyarrow numpy scipy numba pyyaml` and
  `uv add --dev pytest ruff`. Ruff line length 100, rules E, F, I, B, UP; the check must
  pass on scripts/check_milestone.py unchanged. Pytest marker `slow` registered.
- [ ] **Step 3:** Makefile targets:
  `check` = `uv run ruff check .` then `uv run pytest tests -m "not slow" -q`;
  `check-full` = ruff then `uv run pytest tests -q`;
  `hooks` writes `.git/hooks/pre-commit` containing `exec make check` and makes it
  executable; `data` runs download then convert for `DAYS`; `run` and `paper` print
  "not implemented until M2/M6" and exit 1.
- [ ] **Step 4:** `make hooks`, then `make -n check` shows `pytest tests`.
- [ ] **Step 5:** Commit and push.

### Task 2: writing lint

**Files:** Create `tests/test_writing.py`

**Interfaces:** Produces `find_violations(text: str, words: list[str]) -> list[str]`.

- [ ] **Step 1: tests first.** `test_find_violations_catches_word_and_dash`: text
  a sentence holding one banned word in capitals and one em dash gives two hits.
  `test_find_violations_whole_word`: a banned word with a suffix gives none.
  `test_no_banned_words_or_em_dash` parametrised over every linted file.
- [ ] **Step 2:** Implement with `re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE)` and
  a check for U+2014. Linted files: every `.md` from git's file list plus anything under
  `paper/`, excluding `CLAUDE.md`, `.claude/` and `tests/writing_rules.txt`.
- [ ] **Step 3:** Run, all pass. Commit.

### Task 3: split lock (before any download code)

**Files:** Create `src/toxic_flow/data/split_lock.py`, `tests/leakage/test_split_lock.py`
(both protected; expect an approval prompt).

**Interfaces:**
- Produces: `class SplitLockError(RuntimeError)`;
  `load_splits(path: Path = SPLITS) -> dict[str, list[str]]`;
  `split_of(day: str) -> str` (raises `KeyError` for dates in no split);
  `tag_published(repo: Path = ROOT, tag: str = "prereg-v1") -> bool`;
  `assert_allowed(day: str, repo: Path = ROOT) -> str` (returns the split or raises).

- [ ] **Step 1: tests first**, each in a fresh temp repo with a bare repo as `origin`:
  `test_no_tag_refuses_test_day`, `test_local_tag_only_refuses_test_day`,
  `test_tag_on_both_allows_test_day`, `test_train_day_allowed_without_tag`,
  `test_missing_remote_refuses`, `test_local_tag_differs_from_remote_refuses`,
  `test_date_formats_normalised`, `test_unknown_date_refused`.
- [ ] **Step 2:** Run, all fail with import errors.
- [ ] **Step 3:** Implement. `tag_published` runs `git tag --list prereg-v1` and
  `git ls-remote --tags origin prereg-v1`; true only if both list it and the remote
  object id equals `git rev-parse refs/tags/prereg-v1`. Any git error means false.
- [ ] **Step 4:** Run, all pass. Commit.

### Task 4: recon

**Files:** Create `scripts/recon.py`, `data/recon.json`, `docs/DATA_RECON.md`.

- [ ] **Step 1:** GET `https://api.tardis.dev/v1/exchanges/binance-futures`; record in
  `exchange_meta` the BTCUSDT entries of `availableSymbols` and `datasets.symbols`,
  `datasets.exportedFrom/Until`, `dataCollectionDetails`, and incident reports that
  overlap any split date.
- [ ] **Step 2:** HEAD each of the 68 URLs; record `date`, `data_type`, `split`, `url`,
  `method: HEAD`, `status`, `content_length` (int or null), `checked_at`. For train and
  val dates only, also a GET whose body is never read (connection closed after the
  headers) to record the size under `get_headers`; test dates get HEAD only. This
  deviates from "HEAD only" on non-test days and is reported as such.
- [ ] **Step 3:** Size summary per split in docs/DATA_RECON.md.

### Task 5: venue spec

**Files:** Create `configs/venue.yaml`.

- [ ] **Step 1:** Per date: `tick_size`, `lot_size`, `min_notional`, `maker_fee_bps`,
  `taker_fee_bps`, `source`. Sources from Binance pages and dated Wayback snapshots of
  Binance pages and API responses. Unsourced values are `TBD` with a question.
- [ ] **Step 2:** Tick size inferred from the converted benchmark day must match.

### Task 6: download and convert, benchmark day only

**Files:** Create `src/toxic_flow/data/download.py`, `src/toxic_flow/data/convert.py`,
`src/toxic_flow/data/days.py`, `tests/unit/test_download.py`.

**Interfaces:**
- Consumes: `assert_allowed` from Task 3.
- Produces: `resolve_days(arg: str) -> list[str]` (train, val, test or one date);
  `download_day(day: str) -> list[dict]`; `convert_day(day: str) -> Path`.

- [ ] **Step 1: tests first.** `test_download_refuses_test_day_before_tag` (monkeypatched
  network must never be called), `test_existing_file_not_rewritten`,
  `test_hash_mismatch_raises`, `test_manifest_entry_fields`.
- [ ] **Step 2:** Implement. `assert_allowed` is called before any URL is opened. Write to
  a `.part` file, hash while streaming, then rename. Manifest entry: `date`, `data_type`,
  `split`, `url`, `bytes`, `sha256`, `downloaded_at` (UTC ISO 8601), `path`.
- [ ] **Step 3:** `make data DAYS=2024-01-01`; record raw bytes, converted bytes and
  conversion wall time.

### Task 7: engine notes

**Files:** Create `docs/ENGINE.md` with sections Version, Data conversion, Queue models,
Latency models, Exchange model, Fee model. Each name taken from the installed 2.4.4 source
and linked to the v2.4.4 tag on GitHub.

### Task 8: fixed-spread loop and benchmark

**Files:** Create `src/toxic_flow/strategies/b0_fixed.py`, `scripts/benchmark_m0.py`.

- [ ] **Step 1:** Order latency file built from feed latency (multiplier 1, offset 0).
- [ ] **Step 2:** Loop: 100 ms steps, quote from 00:30:00 to 23:59:00 UTC, h = 1 tick,
  bid rounded down and ask rounded up, cancel and replace on change, minimum order size,
  risk-averse queue, no partial fill, fees zero. Record wall time, fill count and peak RSS.
- [ ] **Step 3:** docs/DATA_RECON.md sections Benchmark and Compute projection.

### Task 9: verification

- [ ] `uv run python scripts/check_milestone.py M0` and `make check`, both in the
  transcript; `find data -name '*2025-0[7-9]*'` and the other test dates return nothing.
- [ ] /code-review, then the leakage-auditor on the M0 changes.
