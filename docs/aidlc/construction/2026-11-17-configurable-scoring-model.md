# Construction Plan: Configurable scoring model

**Spec:** [docs/aidlc/inception/2026-11-17-configurable-scoring-model.md](../inception/2026-11-17-configurable-scoring-model.md)
**Date:** 2026-11-17
**Author:** Krrishna

## Design

- **Module.** `backend/apps/matching/scoring.py`. It has four parts:
  - Factor functions, one per name in `FACTORS`: `distance`, `expiry`, `quantity` and `compatibility`. Each takes the
    candidate, `needed`, the requirement `item` and `now`, and returns 0 to 1 (see the spec for the formulas).
  - `FactorScore` (name, value, weight, points), `Score` (total to one decimal, the factors as a tuple) and
    `ScoredCandidate` (the candidate and its score).
  - `ScoringStrategy`, the base class with `name`, `default_weights` and `factors` (the keys of `default_weights`). Its
    `__init__` takes a weights mapping, merges it over the defaults and validates it. `score(candidate, *, needed, item,
    now=None)` returns a `Score`.
  - Three concrete strategies: `EarliestExpiryFirst`, `NearestFirst`, `MostStockFirst`. `STRATEGIES` maps their names
    to the classes.
- **Defaults per resource type.** `DEFAULT_STRATEGY` maps each resource type to its default strategy name. Its keys are
  the values of `ResourceType`, and a test checks that they match.
- **Strategy for a type.** `strategy_for(resource_type)` builds the strategy named in `settings.MATCHING_SCORING` for
  that type, with its resolved weights.
- **Ranking.** `rank(item_candidates, *, now=None)` takes an `ItemCandidates` from #38 and returns a list of
  `ScoredCandidate`, sorted by total descending, then distance ascending with no distance last, then hospital id.
- **Settings.** `backend/config/settings.py` calls `parse_scoring_config(os.environ.get("MATCHING_SCORING", ""))` and
  stores the resolved config in `MATCHING_SCORING`: `{resource_type: {"strategy": name, "weights": {...}}}` for all four
  types. It also sets `MATCHING_MAX_DISTANCE_KM = positive_int_env("MATCHING_MAX_DISTANCE_KM", 50)`.
- **Why settings imports `scoring.py`.** The validator needs the strategy names and default weights, and they live in
  `scoring.py`. So `scoring.py` must load without the app registry. It imports no models at module level. The blood
  shelf life (`SHELF_LIFE_DAYS`) is imported inside the expiry factor, and the factors read `settings` at call time.
- **Validation.** `resolve_weights(strategy, given, *, where)` is the one validation path. `parse_scoring_config` and
  `ScoringStrategy.__init__` both use it. It refuses a factor the strategy does not use, a weight that is negative,
  not a number, not finite or a boolean, and weights that are all zero. Every error is an `ImproperlyConfigured` that
  begins with `MATCHING_SCORING`.
- **Not changed.** `candidates.py`, the API, the frontend, the blood app and the emergencies app. `candidates.py`
  already carries the fields the factors read (`distance_km`, `available`, `earliest_expiry`, `best_donor_rank`).

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Docs: inception and construction plan | `docs/aidlc/inception/2026-11-17-configurable-scoring-model.md`, `docs/aidlc/construction/2026-11-17-configurable-scoring-model.md` | none |
| 2 | Factors, score, strategies, registry, `strategy_for`, `rank`, `parse_scoring_config` | `backend/apps/matching/scoring.py` | `backend/apps/matching/tests/test_scoring.py` |
| 3 | Settings: `MATCHING_SCORING` and `MATCHING_MAX_DISTANCE_KM`, startup validation | `backend/config/settings.py`, `backend/.env.example` | validation cases in `test_scoring.py` |
| 4 | Deployment doc: the two settings with an example | `docs/setup/deployment.md` | none |

## Sequencing

Unit 1 first, as the spec requires. Unit 2 next, then unit 3, since settings import the parser. Unit 4 last.

## Test plan

- Factor edges: distance at 0 km, at the maximum, beyond it and unknown; expiry at expiry-now and at the full
  horizon, and unknown; quantity below, equal to and above the need; compatibility at rank 0, at the worst rank and
  unknown.
- Score: the points add up to the total (within rounding), and the factor names match the strategy.
- Defaults: blood gets `EarliestExpiryFirst`; the other types get `NearestFirst`.
- Ranking: with equal distance, earlier expiry ranks first; with the `mostStock` override, more stock ranks first.
- Configuration: a JSON override changes the weights and the strategy with no code change, through
  `parse_scoring_config` and `strategy_for` under `override_settings`.
- Validation: every error case raises `ImproperlyConfigured`.
- Determinism: every input order of tied candidates gives the same ranking.
- `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run`, then
  `DJANGO_DEBUG=true python manage.py check`, and a bad `MATCHING_SCORING` must fail `check` with the message.
- `pytest` on SQLite and on Postgres.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Verified.** SQLite: 893 passed, 2 skipped, and one failure that is not this story's
  (`apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`, the known SQLite issue). Postgres: 896 passed.
  `test_scoring.py` has 45 tests, all passing. Ruff check and format, `makemigrations --check` and `manage.py check` are
  clean. `MATCHING_SCORING='{"blood":{"strategy":"nope"}}'` fails `manage.py check` with `MATCHING_SCORING (blood):
  unknown strategy 'nope'; use earliestExpiry, nearest, mostStock.`
- **No migration, no API change.** Nothing is stored and the response of `GET /api/emergencies/<ref>/candidates/` is
  unchanged. The order of the candidates is still the #38 order until #41 uses `rank`.
- **Not done here:** the scores and breakdown are not shown (#41). Nothing is reserved or requested (#45). The
  inception doc's sign-off is pending the Product Owner.
