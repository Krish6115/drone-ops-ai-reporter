# Decision Log

## Scope and assumptions

- The application is read-only and requires two numeric board IDs supplied at runtime.
- Monday item names and column values are assumed to be available through the v2 GraphQL `items_page` shape. Every typed value is read through its `text` field to avoid nested JSON interpretation.
- Column titles are not assumed to be identical across offices. Heuristics identify financial, date, sector, status, and stage fields; original source columns remain available for analysis.
- Missing financial values are filled with zero for arithmetic only, while missingness counts are retained in DataFrame metadata and injected into the model context.
- “Leadership Update” means an automated macro-report bridging sales realization and physical field execution: pipeline health, operational completion/bandwidth, and bottlenecks/actions.

## API choice

Monday.com GraphQL API v2 was selected over the Model Context Protocol (MCP) because the delivery window is six hours and the target is a straightforward cloud-hosted Streamlit application. Direct GraphQL with `requests` provides immediate access to cursor pagination, clear read-only boundaries, and predictable JSON that can be cleaned into pandas DataFrames. MCP is an emerging standard for secure AI-tool integrations and is a strong future option, but introducing an MCP server, deployment surface, authentication model, and connector lifecycle would increase delivery risk within this timebox.

## Agent choice

LangChain's `create_pandas_dataframe_agent` was selected because it supports rapid natural-language analysis over the two cleaned DataFrames and keeps the business logic transparent. GPT-4o is configured at temperature 0.2 to favor consistent, grounded answers. The prompt explicitly requires Python/pandas calculations, quality caveats, and a three-paragraph cross-board leadership format.

## Resilience choices

The client uses the required initial `boards.items_page` query and then `next_items_page` cursor queries, a rolling 60-request-per-minute limiter, exponential retries for HTTP 500 and transient request failures, and an explicit cursor-expiration message. Cleaning is non-destructive: source columns are preserved, canonical aliases are added only when useful, and quality metadata is attached to each result.

## Future improvements

- Add schema discovery and configurable per-board column mappings rather than heuristic matching.
- Add automated tests with recorded GraphQL fixtures, including pagination, rate-limit, malformed JSON, and expired-cursor cases.
- Replace arbitrary code execution with a constrained analytical tool layer, approval policy, or a hardened sandbox before multi-tenant production use.
- Add monetary-currency normalization, timezone configuration, data freshness timestamps, and row-level lineage in responses.
- Add persistent cache invalidation, observability, usage budgets, authentication, and role-based access control.
- Evaluate an MCP integration after the deployment and security requirements are stable.
