# Changelog

All notable changes to this project will be documented in this file.

## [Phase 1 - Project Skeleton & Test Harness] - 2026-07-26
- Initialized Django project under `shopgpt2/`.
- Wired up root URL with placeholder home view.
- Added shared `BaseTestCase` with network connection blocker.
- Scaffolded docs directories (`decisions.md`, `design_system.md`).
- Added DB-connected `/health/` check endpoint.
- Implemented and verified POSIX `run_tests.sh` script runner.

## [Phase 2 - Environment, Settings & Logging Hardening] - 2026-07-26
- Split Django configuration into environment settings (`base.py`, `dev.py`, `prod.py`).
- Added `python-dotenv` for safe environment configuration loading.
- Created `.env.example` placeholder and `.gitignore` file.
- Cleaned and pinned `requirements.txt` dependencies.
- Configured structured logging with console and file rotation output.
- Set up custom 404 and 500 error views.

## [Phase 3 - Accounts App — Auth & Forms] - 2026-07-26
- Scaffolded `accounts` Django app.
- Created `LoginForm` with case-insensitive username handling.
- Implemented `SignupForm` with custom validation and terms acceptance requirements.
- Added class-based login (`UserLoginView`) and signup (`UserSignupView`) views.
- Created session-clearing logout view (`user_logout`).
- Integrated Django's default password reset views with namespaced redirection routing support.
- Fully verified all auth components with 19 new unit tests (35 total).

## [Phase 4 - Core Models & Migrations (Products, ScrapeHistory)] - 2026-07-26
- Created the `products` Django application.
- Implemented `SearchQuery` (scraped query history) and `ProductResult` (scraped product detail) database models.
- Set up database indexing on foreign keys and the `platform` field to optimize query execution.
- Configured initial schema migrations and applied them cleanly.
- Registered both models inside the Django Admin console with customized list displays, filters, and searches.
- Verified database models, field types, constraint validation, and admin endpoints with 4 new unit tests (39 total tests passing).

## [Phase 5 - Guest Limits, Sessions & Security] - 2026-07-26
- Implemented `GuestSearchLimitMiddleware` to intercept search requests and enforce guest POST search limits.
- Set up automated session counter cleanup on successful login/signup authentication.
- Replaced root `/` placeholder with a dynamic static copy `HomeView` context.
- Added cache-backed rate limiting with lockouts and cooldown periods inside `LoginForm` authentication flow.
- Added 9 unit tests checking lockouts, session cleanups, and guest middleware limits.

## [Phase 6 - Managers, Validation & Factories] - 2026-07-26
- Built field-validators for `ProductResult` validating non-negative price, URL formats, and allowed platforms choices.
- Implemented `mark_completed` and `mark_failed` status updating helpers on `SearchQuery`.
- Created custom `SearchQueryManager` with `recent_for_user` logic and `ProductResultManager` with `for_search` sorting.
- Developed `save_results` atomic service utility handling bulk creations and status transitions.
- Created reusable test factories inside `products/factories.py`.
- Wrote 6 extensive tests covering validation constraints, factories, and managers.

## [Phase 7 - Integrations API Client Core] - 2026-07-26
- Scaffolded `integrations` Django application and registered it in settings.
- Created generic `ProductDTO` data transfer object and abstract interface `ProductAPIClient`.
- Implemented concrete `SerpApiClient` wrapping the Google Shopping search API with regex-based price parsing, merchant platform mapping, and malformed row skipping.
- Created `NullAPIClient` fallback logging warning when keys are unconfigured.
- Added 6 new unit tests verifying mock client requests, DTO validation, and parsing edge cases (60 total tests passing).

## [Phase 8 - Integrations Layer — Resilience, Caching & Config] - 2026-07-26
- Added timeout constraints and retries with exponential backoffs to SerpApi requests.
- Integrated HTTP 429 rate limit backoff and Retry-After header handling.
- Implemented multi-page pagination limits.
- Configured dynamic cache connection setups supporting Redis or LocMem fallbacks.
- Masked and redacted raw API keys inside outbound logger trace outputs.
- Added Django AppConfig provider validation startup checks.
- Wrote 8 tests covering retries, 429 headers, pagination caching, and configuration alerts (68 total tests passing).

## [Phase 9 - Search Orchestration — Service Layer] - 2026-07-26
- Created main `SearchService.run` coordinating retrieval, cleaning, and database persistence.
- Implemented optional asynchronous background Celery tasks with automated socket-based synchronous fallbacks.
- Built URL normalization and difflib SequenceMatcher title similarity checks for DTO de-duplication.
- Mapped client failures to database-backed failure reason fields.
- Added 7 tests checking de-duplications, error mappings, and Celery dispatch fallbacks (75 total tests passing).

## [Phase 10 - Search Orchestration — Views, Errors & History] - 2026-07-26
- Implemented `SearchView` routing and processing queries with redirect dispatch logic.
- Built `ResultsView` showing clean list views or custom honest failure states.
- Created `ComparisonView` supporting sorting by price/rating and asc/desc directions.
- Developed `TopRecommendationsView` selecting the cheapest top 3 in-stock products with reason labels.
- Added `HistoryView` displaying the logged-in user's past queries securely.
- Wired standard error copy mapping logic across all result-dependent views.
- Added 6 tests checking views, sorting, and history security bounds (81 total tests passing).

## [Phase 11 - Analytics — Data Loading, Cleaning & Aggregation] - 2026-07-26
- Scaffolded `analytics` Django application.
- Implemented `load_results_df` converting database objects to standard pandas DataFrames.
- Developed cleaning pipeline `clean_df` resolving duplicates, missing prices, and applying sentinel values.
- Built platform price aggregations and summary statistics logic.
- Developed numerical correlation matrices computation.
- Implemented IQR price outlier detection per platform.
- Wrote 6 unit tests validating loading, deduplication, correlations, and IQR boundaries (87 total tests passing).

## [Phase 12 - Analytics — Chart-Data Builders] - 2026-07-26
- Created `AnalyticsSnapshot` model storing aggregations, counts, desc summaries, and correlations in JSON format.
- Added recursive float NaN/Inf JSON sanitizer helper preventing SQLite JSON check constraints failures.
- Implemented `refresh_analytics` Django management command.
- Built price distribution histogram bins data calculator.
- Developed per-platform price boxplot data and scatter data coordinate builders.
- Built server-side static chart image PNG exporter using Seaborn and matplotlib.
- Added Plotly interactive chart figure dictionary schema generators.
- Added 7 tests validating snapshot saving, command execution, data builders, PNG file signature checks, and Plotly schema traces (94 total tests passing).






