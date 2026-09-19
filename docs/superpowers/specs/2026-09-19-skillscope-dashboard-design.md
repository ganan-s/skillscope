# Skillscope dashboard design specification

## Product scope

v1 dashboard: a localhost web app served by `skillscope serve` that displays
closed conversations and the skill files they loaded. Read-only. No ingest,
evaluation, live filesystem access, or write actions at serve time.

## Information architecture

Three-level working surface:

1. **Repository rail** (left): repositories derived from stored workspace path
   basenames. Full path on hover. Multi-workspace conversations appear under
   each applicable repository group.
2. **Thread list** (center-left): the selected repository's conversations,
   newest first. Each row shows title, relative date, skill count, and an
   explicit "No skills" state for zero-activation threads.
3. **Main canvas** (center-right): the selected thread rendered as a
   chronological prompt-to-skill causal spine:
   - Prompt
     - Skill activation
     - Skill activation
   - Next prompt
     - Skill activation

Selecting an activation opens a right-side **evidence inspector** showing
captured `SKILL.md` content, description, source, path, timestamp/provenance,
repeat count, and resource reads.

The URL preserves selected conversation and activation for refresh and back
navigation. Repository collapse and display preferences are ephemeral browser
state.

## Visual direction

Editorial developer tool: monochrome, quiet, precise.

- **Palette**: warm white background, true white surfaces, near-black text,
  short neutral-gray scale. Black for selection and primary emphasis. No
  gradients or colored status indicators.
- **Typography**: bundled refined sans for navigation and content; compact
  monospace only for paths, timestamps, and captured files. Weight and spacing
  for hierarchy, not oversized display text.
- **Surfaces**: thin hairline dividers, minimal card stacking, small-radius
  controls, one restrained shadow on the evidence inspector.
- **Density**: compact thread navigation, generous reading width in the main
  canvas, clear vertical rhythm between prompts.
- **Motion**: 120-180ms transitions for rail expansion, active-row movement,
  and inspector entry. No decorative animation.
- **Skill source labels**: grayscale text (`Project`, `User`, `Built-in`,
  `Unknown`), not color-coded pills.

The memorable element is structural: a clean vertical causal spine connecting
each prompt to the skills loaded beneath it.

## Architecture

### Backend

- Application query models and ports in `skillscope.application.queries`.
- SQLite read adapter in `skillscope.storage.readers` implementing query ports.
- Pydantic response schemas in `skillscope.api.schemas`.
- FastAPI routes in `skillscope.api.app`.
- Composition wiring in `skillscope.bootstrap`.
- `skillscope serve` CLI subcommand in `skillscope.cli`.

Domain and application layers remain independent of FastAPI, SQLite, and
frontend code per the hexagonal architecture.

### Frontend

- React + TypeScript + Vite + Tailwind in a `web/` workspace at project root.
- Vite output directed to `src/skillscope/web/dist/` for Python package
  inclusion.
- Development: Vite dev server proxying `/api/v1` to the backend.
- Production: static assets mounted by FastAPI after API routes, with SPA
  fallback for non-API paths only.

### Data loading

- Fetch conversation summaries in pages of 100, continuing in the background
  until complete. This gives full repository grouping without loading full
  transcripts.
- Fetch one conversation detail only when selected.
- Retain successful navigation context on errors; support inline retry.

### Grouping

- Derive repository labels from stored workspace path strings in the frontend.
- Never touch the live filesystem.
- A conversation with multiple workspace paths appears under each applicable
  repository group.

### Navigation

- Conversation and activation selection live in the URL.
- Repository collapse and display preferences are ephemeral browser state.

## Explicit states

- **Missing/unusable store**: dedicated screen with the safe next command.
- **Empty store**: explain that no closed conversations have been ingested.
- **No skill activation**: preserve the prompt, show "No skills invoked."
- **Missing captured payload**: show metadata and stored unavailable reason.
- **API/detail failure**: inline retry without discarding navigation context.

## v1 exclusions

No search, pinning, archive, rename, delete, ingest button, evaluation
placeholder, live refresh, or write actions.

## API boundary

The frontend uses only the three existing read-only endpoints from the OpenAPI
contract (`docs/openapi/v1.yaml`):

- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `GET /api/v1/meta`

## Verification

- Backend unit tests for projection/ordering logic.
- Backend integration tests against temporary migrated SQLite stores covering
  pagination, empty stores, zero-skill conversations, unavailable payloads,
  errors, and static fallback routing.
- Frontend tests for repository grouping and prompt/activation ordering.
- Production build verification.
- End-to-end smoke: seeded database to rendered thread detail.
