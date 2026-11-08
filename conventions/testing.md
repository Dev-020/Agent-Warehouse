---
id: convention/testing
version: 0.1.0
status: draft
summary: Generic rules for writing tests and keeping a project's main test suite fast, deterministic and trusted.
applies-to: [codebase, warehouse]
settings: {}
requires: []
replaces: null
---

# Testing Convention

Generic rules for writing durable tests and keeping a project's main test suite fast, deterministic and
trusted, in any language. Project-specific testing decisions and agent instructions follow
[[test-planning]] and are recorded in the project's [[test-plan]].

## 1. Size and scope

**Size** classifies a test by what resources it may use; **scope** classifies it by how much code it
is meant to verify.

| Size | Allowed resources | Forbidden resources |
|---|---|---|
| **Small** | One process (usually one thread); in-memory filesystem | Sleeping, disk or network I/O, blocking calls |
| **Medium** | One machine: multiple processes or threads, blocking calls, `localhost` network | Any system outside `localhost` |
| **Large** | Multiple processes or machines; full system dependencies | — |

- **Scope** is narrow (**unit**: one focused module or class), medium (**integration**: interactions
  between a small number of components), or large (**end-to-end**: several parts of the system).
- Keep narrow tests small whenever possible; mark every non-small test explicitly so the test runner
  can filter by size.

Source: *Software Engineering at Google*, ch. 11 (Titus Winters, Tom Manshreck, Hyrum Wright; O'Reilly 2020, https://abseil.io/resources/swe-book/html/ch11.html).

## 2. Time budget per size

Each test target has a maximum runtime set by its size:

| Size | Default timeout per test |
|---|---|
| **Small** (`short`) | 60 s |
| **Medium** (`moderate`) | 300 s |
| **Large** (`long`) | 900 s |
| **Enormous** (`eternal`) | 3600 s |

- The default test run (small tests, plus medium tests if the project's test plan includes them) has a
  wall-clock budget set in the test plan ([[test-planning]] default: **10 minutes**).
- Going over a per-test or suite time budget is a defect: record it in the [[backlog]] and split or
  speed up the slow tests instead of accepting the slower run.

Source: Bazel Test Encyclopedia (Google, https://bazel.build/reference/test-encyclopedia).

## 3. Hermetic and order-independent

- Every test contains its own setup and teardown—temp directories, windows, threads, globals,
  environment variables, and clock—and writes only to its own private temp directory.
- Every test must pass when run alone, in the full run, and in random order.
- A test that passes alone but fails in the full run has a state-leak bug (described in secondary
  summaries of Meszaros's *xUnit Test Patterns* as interacting tests sharing state); practitioner
  reports advise detecting order dependence by running tests alone and in randomized order.

Source: *Software Engineering at Google*, ch. 11 (Winters, Manshreck, Wright, https://abseil.io/resources/swe-book/html/ch11.html); Bazel Test Encyclopedia (https://bazel.build/reference/test-encyclopedia); Gerard Meszaros, *xUnit Test Patterns* (Addison-Wesley 2007, secondary summary via https://test-smell-catalog.readthedocs.io/).

## 4. Writing tests

- **Test through the public API:** verify behaviour that callers rely on, not private methods or
  internal implementation details.
- **One behaviour per test (given / when / then):** structure each test into setup (given), action
  (when), and verification (then), with no control-flow logic (conditionals or loops) inside the test.
- **Clear failure messages and DAMP style:** failure messages must state the expected result, the
  actual result, and the inputs; prefer DAMP (*Descriptive And Meaningful Phrases*) over strict DRY so
  each test is complete and readable on its own.
- **Write unchanging tests:** refactors, bug fixes, and unrelated features must not require editing
  existing tests; never pin values that change with every feature, such as total counts or full lists
  of a registry.

Source: *Software Engineering at Google*, ch. 12 (Winters, Manshreck, Wright, https://abseil.io/resources/swe-book/html/ch12.html); Ham Vocke, "The Practical Test Pyramid" (2018, https://martinfowler.com/articles/practical-test-pyramid.html).

## 5. Building test state

- Build precondition state directly (or with helper functions that provide sensible defaults), not by
  driving earlier steps through the code under test.
- Call the code under test only for the behaviour that the test is verifying.
- Share expensive setup only through a read-only template copied per test, never through a fixture
  that tests mutate in place (which secondary summaries of Meszaros note causes interacting tests).

Source: pytest documentation, "How to use fixtures — Scope" (https://docs.pytest.org/en/stable/how-to/fixtures.html); *Software Engineering at Google*, ch. 12 (Winters, Manshreck, Wright, https://abseil.io/resources/swe-book/html/ch12.html); Gerard Meszaros, *xUnit Test Patterns* (Addison-Wesley 2007, secondary).

## 6. Test doubles

- Choose dependencies in this order: **real implementation** first (when fast, deterministic, and
  simple), then **fake**, then **stub**, then **interaction check**.
- Give every fake its own contract tests so it stays faithful to the real implementation.
- Use interaction checks only for functions that change state; prefer asserting resulting state over
  asserting call sequences so tests do not become brittle change-detectors.

Source: *Software Engineering at Google*, ch. 13 (Winters, Manshreck, Wright, https://abseil.io/resources/swe-book/html/ch13.html).

## 7. Speed

- Poll or wait for events instead of sleeping for fixed durations.
- Split a slow, broad test into smaller tests that can run independently and in parallel.
- Keep large tests out of the default run so the suite stays fast enough to run routinely.

Source: *Software Engineering at Google*, ch. 11 & 14 (Winters, Manshreck, Wright, https://abseil.io/resources/swe-book/html/ch14.html).

## 8. Flaky tests

- A flaky test is one that passes and fails on the same code without changes.
- Fix a flaky test at once, or quarantine it with a [[backlog]] entry naming the test; never merge on
  test failures that are not recorded in the backlog.
- A retry may confirm that a failure is flaky, but it is never the fix; near 1% flakiness a test suite
  begins to lose its value because engineers stop trusting failures.

Source: *Software Engineering at Google*, ch. 11 (Winters, Manshreck, Wright, https://abseil.io/resources/swe-book/html/ch11.html); John Micco, "Flaky Tests at Google and How We Mitigate Them" (Google Testing Blog, 27 May 2016, https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html).

## 9. Coverage and quality signals

- Coverage shows only which lines ran, not whether assertions verified the result; use it as a hint to
  find untested code, never as a numeric target or ceiling.
- Mutation testing on changed lines is the stronger quality signal where a tool exists.

Source: *Software Engineering at Google*, ch. 11 (Winters, Manshreck, Wright, https://abseil.io/resources/swe-book/html/ch11.html); Goran Petrović et al., "Practical Mutation Testing at Scale: A view from Google" (IEEE TSE 2021, https://research.google/pubs/practical-mutation-testing-at-scale-a-view-from-google/).

## 10. Tests written by agents

Coding agents add mocks significantly more often than human developers (Hora & Robbes 2026), and recent
preprints and practitioner reports warn that agent-written tests carry higher flakiness risk from file
I/O and non-deterministic logic (reported by Jhanglani et al. 2026) and often consist of print-statement
probes rather than real assertions (reported by Chen et al. 2026 via Vaughan). Every agent-written test
must follow these rules:

- (a) a test asserts something; a test that only prints is a probe;
- (b) no new mock without a stated reason;
- (c) file I/O only in temp dirs, seeds fixed, no real clock;
- (d) an assertion is never weakened, skipped or deleted without saying so in the report;
- (e) probes live outside the suite unless promoted on purpose.

Source: André Hora & Romain Robbes, "Are Coding Agents Generating Over-Mocked Tests? An Empirical Study" (MSR '26, https://arxiv.org/abs/2602.00409); Jhanglani et al., "Beyond Test Presence: Assessing the Quality and Robustness of Agent-Generated Tests in Open-Source Projects" (preprint, https://arxiv.org/abs/2607.12068); Chen et al., "Rethinking the Value of Agent-Generated Tests for LLM-Based Software Engineering Agents" (preprint, arXiv:2602.07900, reported by Daniel Vaughan, https://codex.danielvaughan.com/2026/05/02/do-agent-written-tests-actually-help-codex-cli-testing-strategy/).

## 11. One main suite, one command

- Tests live in one place and run with one recorded default command, plus named commands for marked
  larger tests.
- The commands are recorded in the project's test plan ([[test-planning]], [[test-plan]]).

Source: *Software Engineering at Google*, ch. 11 & 14 (Winters, Manshreck, Wright, https://abseil.io/resources/swe-book); Bazel Test Encyclopedia (Google, https://bazel.build/reference/test-encyclopedia).

## 12. Sources

Primary and peer-reviewed references:
- Titus Winters, Tom Manshreck, Hyrum Wright, *Software Engineering at Google*, ch. 11 (Testing Overview), ch. 12 (Unit Testing), ch. 13 (Test Doubles), ch. 14 (Larger Testing), O'Reilly 2020 — https://abseil.io/resources/swe-book
- Google, *Bazel Test Encyclopedia* — https://bazel.build/reference/test-encyclopedia
- Ham Vocke, "The Practical Test Pyramid", martinfowler.com, 26 Feb 2018 — https://martinfowler.com/articles/practical-test-pyramid.html
- Kent C. Dodds, "The Testing Trophy and Testing Classifications", 3 Jun 2021 — https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications
- John Micco, "Flaky Tests at Google and How We Mitigate Them", Google Testing Blog, 27 May 2016 — https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html
- Goran Petrović, Marko Ivanković, Gordon Fraser, René Just, "Practical Mutation Testing at Scale: A view from Google", IEEE TSE 2021 — https://research.google/pubs/practical-mutation-testing-at-scale-a-view-from-google/
- André Hora, Romain Robbes, "Are Coding Agents Generating Over-Mocked Tests? An Empirical Study", MSR '26 — https://arxiv.org/abs/2602.00409
- pytest documentation, "Good Integration Practices" and "How to use fixtures" — https://docs.pytest.org/en/stable/explanation/goodpractices.html , https://docs.pytest.org/en/stable/how-to/fixtures.html

Secondary summaries, preprints, and practitioner reports (cited as advice or "reported by" above):
- Gerard Meszaros, *xUnit Test Patterns: Refactoring Test Code*, Addison-Wesley 2007 (secondary summaries via https://test-smell-catalog.readthedocs.io/ and https://dotnetweb30-ke.gitbook.io/ke/verification/automated-testing-principles-patterns-and-practices/test-smells-and-how-to-avoid)
- Jhanglani, Desai, Kansara, AlOmar, "Beyond Test Presence: Assessing the Quality and Robustness of Agent-Generated Tests in Open-Source Projects", preprint 2026 — https://arxiv.org/abs/2607.12068
- Chen et al., "Rethinking the Value of Agent-Generated Tests for LLM-Based Software Engineering Agents", arXiv:2602.07900, reported by Daniel Vaughan, 2 May 2026 — https://codex.danielvaughan.com/2026/05/02/do-agent-written-tests-actually-help-codex-cli-testing-strategy/
- Practitioner flaky-test reports (2026) — https://testdino.com/blog/flaky-test-benchmark , https://dev.to/rollamadugu/flaky-tests-arent-random-a-field-guide-to-finding-and-killing-them-1bnp

Source: *Software Engineering at Google*, ch. 11–14 (Winters, Manshreck, Wright, https://abseil.io/resources/swe-book); Bazel Test Encyclopedia (https://bazel.build/reference/test-encyclopedia); Ham Vocke (https://martinfowler.com/articles/practical-test-pyramid.html); Kent C. Dodds (https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications); John Micco (https://testing.googleblog.com/2016/05/flaky-tests-at-google-and-how-we.html); Hora & Robbes (https://arxiv.org/abs/2602.00409).

## Changelog

### [Unreleased]
#### Added
- First draft.
