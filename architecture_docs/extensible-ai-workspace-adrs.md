# Architecture Decision Records: Extensible AI Workspace

## Document Control

| Field | Value |
|---|---|
| Document | Consolidated Architecture Decision Records |
| Product | Extensible AI Workspace |
| Version | 1.0 |
| Status | Accepted baseline for implementation |
| Owner | Jason Macfarlane |
| Related documents | PRD v1.0; HLA v1.0; TDD v1.0; Data Design Document v1.0; API Contract v1.0 |

## Purpose

This document consolidates the consequential architecture decisions for Extensible AI Workspace. Each record captures the context, accepted decision, alternatives, rationale, consequences, implementation guardrails, and conditions that would justify revisiting it.

These ADRs summarize decisions already accepted in the design documents. They do not repeat every implementation detail or replace the PRD, HLA, TDD, Data Design Document, or API Contract.

---

# ADR-001: Modular Monolith with Separate Worker Runtime

## Status

Accepted

## Context

The product requires persistent workspaces, long-running AI workflows, approvals, source processing, tool execution, progress reporting, and recoverable background-style work. It is being developed initially by one developer for one user per deployment. Starting with independently deployed business microservices would add distributed transactions, network failure handling, service authentication, versioned service contracts, local-development complexity, and additional observability infrastructure before the product validates its flagship workflow.

A single request-serving process alone would make long-running research, parsing, retries, recovery, and approval pauses difficult to isolate from interactive web traffic.

## Decision

Build one cohesive modular-monolith application and codebase, packaged as one application image, with two runtime roles:

- Web runtime for server-rendered HTML, HTMX, JSON APIs, authentication, authorization, validation, workflow submission, approval commands, status delivery, and artifact views.
- Worker runtime for durable execution segments, source processing, workflow orchestration, provider calls, tool execution, retries, reconciliation, and artifact generation.

The web and worker run as separate processes or containers but share application modules, contracts, releases, and PostgreSQL state.

## Alternatives Considered

- One monolithic web process performing both interactive and long-running work.
- Microservices from the beginning.
- Separate codebases and images for web and worker.

## Rationale

This design isolates long-running work without taking on full microservice complexity. It supports independent worker scaling later, preserves simple local development, and lets module boundaries mature before service extraction is considered.

## Positive Consequences

- Simpler development and deployment than microservices.
- Interactive requests are isolated from long-running work.
- One codebase and image reduce release compatibility burden.
- Modules may later be extracted if measured needs justify it.
- Local composition remains understandable.

## Negative Consequences

- Web and worker share a release lifecycle.
- PostgreSQL becomes a critical shared dependency.
- Module boundaries must be enforced by code structure and tests rather than network isolation.
- Local deployment operates more than one process.

## Implementation Guardrails

- Workflow-specific modules depend on generic platform modules, not the reverse.
- Modules do not modify another module's tables directly.
- Long-running work does not execute in request handlers.
- Additional deployable services require measured scaling, isolation, ownership, or deployment justification.

## Revisit When

- Worker and web release cadences must become independent.
- A module requires materially different scaling or security isolation.
- Team ownership boundaries justify service extraction.
- PostgreSQL coordination or shared deployment becomes a measured operational bottleneck.

---

# ADR-002: PostgreSQL as Authoritative State and Durable Coordination

## Status

Accepted

## Context

The platform needs durable workspace state, workflow lifecycle, jobs, approvals, messages, sources, provenance, artifacts, provider calls, tool executions, events, sessions, and retrieval metadata. It also needs work submission, safe worker claiming, leases, retries, and transactional post-commit events.

Adding Redis or a dedicated broker solely because task queues commonly use one would increase deployment and consistency complexity for a bounded single-user workload.

## Decision

Use PostgreSQL as:

- The authoritative store for durable platform and business state.
- The MVP coordination mechanism between the web and worker runtimes.
- The transactional-outbox store.
- The initial lexical-search and vector-search platform, subject to evaluation.

Workers claim eligible jobs with `FOR UPDATE SKIP LOCKED`, then persist worker identity, lease identity, lease expiry, and attempt state. Leases are renewable during active execution.

Use short explicit transactions at application-use-case and durable-workflow boundaries. Repositories participate in an application-controlled Unit of Work and never commit independently.

## Alternatives Considered

- Redis-backed task queue.
- Dedicated message broker.
- PostgreSQL advisory locks as the primary ownership mechanism.
- Status updates without row locking.
- Long database transactions around complete workflow execution.

## Rationale

PostgreSQL is already required for durable state. It can coordinate the expected workload without another required service and allows state changes, jobs, and outbox records to commit atomically.

## Positive Consequences

- Fewer required infrastructure components.
- Durable jobs survive process restarts.
- Job, workflow, and approval state remain queryable in one system.
- Transactional outbox prevents lost post-commit reactions.
- Safe multi-worker claiming is available when needed.

## Negative Consequences

- Job claiming, leases, heartbeats, and recovery require careful implementation.
- PostgreSQL receives both application and coordination workload.
- Polling and event retention need tuning.
- External side effects still cannot participate in PostgreSQL transactions.

## Implementation Guardrails

- Queue state and workflow state remain separate concepts.
- No database transaction remains open across model, search, tool, storage, or human waits.
- An expired lease permits recovery, not blind restart.
- A worker verifies active lease ownership before committing results.
- Outbox delivery and event handlers are at least once and idempotent.
- Redis or a broker is introduced only after measurement demonstrates need.

## Revisit When

- Job throughput or latency exceeds PostgreSQL coordination capacity.
- Multiple web instances require more efficient transient event distribution.
- Independent consumers require broker routing or durable subscription semantics.
- Coordination workload materially impacts core transactional performance.

---

# ADR-003: Lean Server-Rendered HTMX Interface with JSON and SSE Contracts

## Status

Accepted

## Context

The product requires workspace navigation, conversations, source management, progress, approvals, findings, artifact previews, downloads, and settings. The frontend should remain lean and should not consume disproportionate project effort. Future workflows may be unrelated to research and may need specialized views.

A React-style SPA would introduce build, state-management, authentication, and client-rendering complexity. HTML-only routes would weaken future programmatic access and streaming semantics.

## Decision

Use:

- Server-rendered HTML with HTMX-style progressive enhancement for the browser.
- JSON contracts under `/api/v1` where machine-readable access has concrete value.
- Server-Sent Events for one-way progress and output snapshots.
- Ordinary authenticated HTTP for commands, forms, approvals, and cancellation.
- Polling fallback for environments where SSE is unavailable.

Provide a stable workflow-oriented application shell with reusable components for progress, approvals, tool activity, artifacts, errors, and source selection. Allow optional trusted workflow-specific server-rendered views.

## Alternatives Considered

- Full SPA using React or another heavy framework.
- HTML/HTMX endpoints only.
- JSON REST API for every browser interaction.
- WebSockets for all live communication.

## Rationale

HTMX supports the required interactions with less frontend complexity. JSON and SSE preserve a credible application boundary, while platform workflow descriptors keep the shell extensible without building a universal metadata-driven UI.

## Positive Consequences

- Faster implementation and simpler debugging.
- Minimal browser JavaScript.
- Good fit for server-side sessions and CSRF.
- Live progress without WebSocket complexity.
- Future clients can use documented JSON contracts.
- Specialized workflows require localized views rather than shell rewrites.

## Negative Consequences

- Some interactions require both HTML and JSON presentation models.
- HTMX fragment conventions need documentation and tests.
- Rich client-side interactions may require targeted JavaScript later.
- A new workflow may still need a specialized view.

## Implementation Guardrails

- Browser presentation never owns workflow, approval, or execution authority.
- Critical state-changing forms use CSRF protection and server validation.
- Untrusted source, message, evidence, and artifact content is escaped or sanitized.
- No universal dynamic UI builder is implemented.
- Full artifact content is loaded through protected endpoints, not embedded in list responses.

## Revisit When

- Required interaction complexity becomes consistently difficult in server-rendered views.
- Offline-first or mobile clients become product requirements.
- Bidirectional low-latency interaction becomes necessary.
- A richer client can be justified by measured user-value improvements.

---

# ADR-004: Controlled Workflows with Bounded Agentic Stages

## Status

Accepted

## Context

The platform must support flexible AI reasoning and tool selection while preserving predictable lifecycle, source scope, approval, recovery, evaluation, cancellation, and resource control. A fully autonomous agent loop would make completion, retries, approvals, and testing difficult. Fully deterministic workflows would be unnecessarily rigid for research tasks.

## Decision

Use explicit workflow definitions with deterministic platform control over:

- Lifecycle state.
- Permissions and source scope.
- Allowed tools by stage.
- Approval checkpoints.
- Retry and cancellation policy.
- Completion conditions.
- Durable state and progress.
- Resource budgets.

Permit model-driven reasoning or dynamic tool selection only within explicitly bounded stages. Each workflow maps internal stages to a shared platform lifecycle and declares its inputs, outputs, allowed tools, approval points, budgets, error conditions, and optional specialized view.

## Alternatives Considered

- Autonomous general-purpose agent.
- Fully predefined deterministic workflow without agentic stages.

## Rationale

Bounded agentic stages provide flexibility where model reasoning adds value while keeping the system testable, auditable, recoverable, and safe.

## Positive Consequences

- Predictable outer workflow lifecycle.
- Explicit approval and recovery boundaries.
- Easier deterministic testing and AI evaluation.
- Resource use can be bounded.
- Future non-research workflows reuse the same platform lifecycle.

## Negative Consequences

- Workflow authors must define boundaries and policies deliberately.
- Agentic flexibility is constrained.
- Poorly designed stages may still leak policy into prompts.
- More design effort than a simple agent loop.

## Implementation Guardrails

- Models may recommend actions but cannot authorize them.
- Models cannot expand source permissions, budgets, or tool access.
- Every agentic loop has iteration and usage limits.
- Workflow completion is determined by workflow policy, not solely by model judgment.
- Source content and tool output remain lower-authority context.

## Revisit When

- Evaluation demonstrates that bounded stages materially prevent useful tasks.
- New workflow categories require a different execution model.
- Stronger autonomous behaviour can be introduced with equally strong safety, recovery, and evaluation guarantees.

---

# ADR-005: Platform-Owned Lifecycle with Runtime-Owned LangGraph Checkpoints

## Status

Accepted

## Context

LangGraph is a strong candidate for graphs, nodes, edges, conditional routing, interruption, and continuation. However, making LangGraph threads, checkpoints, or Store the product's authoritative domain model would couple approvals, UI, authorization, reporting, and non-LangGraph workflows to one orchestration framework.

Reimplementing every runtime detail in platform tables would duplicate orchestration capabilities and create a custom workflow engine.

## Decision

The platform owns authoritative:

- Workflow identity, type, and version.
- Workspace and user ownership.
- Common lifecycle status and user-visible stage.
- Progress, cancellation, completion, and recovery state.
- Jobs, approvals, tool executions, sources, findings, artifacts, and operational records.
- Conversations, workspace knowledge, and explicit user memory.

LangGraph or another workflow runtime may durably own workflow-run-scoped continuation state, including graph position, conditional branch details, bounded iteration state, and temporary values needed to resume execution.

LangGraph's cross-thread long-term-memory Store is not the authoritative application-memory layer.

## Alternatives Considered

- LangGraph owns all workflow and application state.
- Platform database owns every runtime detail and reconstructs the graph manually.

## Rationale

This split uses LangGraph where it provides value without making it the product domain model. It preserves framework replacement, non-LangGraph workflows, queryable lifecycle state, and platform-controlled memory semantics.

## Positive Consequences

- UI and approval modules do not inspect graph internals.
- Runtime checkpoints can support interruption and recovery.
- Platform state remains queryable and independently understandable.
- Future workflow runtimes can coexist.
- Cross-workspace memory remains explicit and governed.

## Negative Consequences

- Platform lifecycle and runtime checkpoint state must remain compatible.
- Workflow upgrades require checkpoint-compatibility rules.
- Missing or stale checkpoints need recovery handling.
- Developers must avoid copying the entire application database into graph state.

## Implementation Guardrails

- Checkpoints normally contain stable references rather than full documents, conversations, approvals, artifacts, or tool histories.
- Every run records workflow, runtime, and checkpoint versions.
- Incompatible or missing checkpoints enter `RECOVERY_REQUIRED` rather than restarting automatically.
- If replacing LangGraph would not remove the need for a fact, that fact belongs to platform-owned state.

## Revisit When

- LangGraph becomes unsuitable for the chosen workflows.
- Runtime/platform synchronization creates disproportionate complexity.
- A different orchestration engine provides a stronger durable-execution model without replacing platform ownership.

---

# ADR-006: PostgreSQL Job Claiming, Renewable Leases, Durable Segments, and At-Least-Once Processing

## Status

Accepted

## Context

Workers may crash, lose database connectivity, time out during external calls, or resume workflows after approval. The platform must prevent simultaneous normal ownership while acknowledging that exactly-once execution across external systems cannot be guaranteed.

A job per LangGraph node would expose runtime internals. One job for an entire workflow would create coarse recovery and long leases.

## Decision

- Claim jobs transactionally with `FOR UPDATE SKIP LOCKED`.
- Persist worker and lease identity, lease expiry, and attempt information.
- Renew leases while active.
- Execute one durable workflow segment per claimed job.
- Let a segment contain one or more internal graph nodes.
- End a segment at meaningful recovery, approval, retry, cancellation, long-operation, state-changing-tool, completion, or budget boundaries.
- Process jobs at least once with stable execution IDs, idempotency keys where supported, persisted outcomes, and reconciliation of uncertain side effects.
- Preserve each job attempt separately.

## Alternatives Considered

- Exactly-once execution assumption.
- At-least-once retry without shared safeguards.
- One job for a complete workflow.
- One job per LangGraph node.
- Advisory locks as the only ownership mechanism.

## Rationale

The selected model is honest about distributed failure and provides recoverable, bounded execution without coupling job coordination to framework nodes.

## Positive Consequences

- Multiple workers can claim distinct jobs safely.
- Worker crashes are recoverable after lease expiry.
- Approval waits do not retain worker leases.
- State-changing operations can be isolated.
- Job-attempt history supports diagnosis.
- Non-LangGraph workflows use the same execution model.

## Negative Consequences

- Lease and heartbeat timing require tuning.
- Some uncertain outcomes require manual or automated reconciliation.
- Segment boundaries add workflow-author responsibility.
- At-least-once delivery requires idempotent handlers and tools where possible.

## Implementation Guardrails

- Stale workers cannot commit over a current lease holder.
- A paused workflow completes its current job and releases ownership.
- Expired leases trigger recovery inspection, not restart from the first stage.
- Unsafe uncertain actions are never retried automatically.
- Segment budgets bound time, calls, iterations, retrieval, and retries.

## Revisit When

- Measured job throughput requires a dedicated queue or broker.
- Segment overhead becomes material.
- External systems provide stronger transactional or idempotency guarantees that can simplify reconciliation.

---

# ADR-007: First-Class Human Approvals and Idempotent State-Changing Execution

## Status

Accepted

## Context

The platform can propose web-research expansion, external file exports, and future state-changing tool actions. Approval must survive restarts, apply only to the action reviewed by the user, prevent replay, and remain independently auditable.

A Boolean approval flag or workflow-status field cannot represent expiry, rejection, supersession, consumption, multiple approvals, or exact proposal identity.

## Decision

Model approval as a first-class durable resource with states:

- `PENDING`
- `APPROVED`
- `REJECTED`
- `EXPIRED`
- `SUPERSEDED`
- `CANCELLED`
- `CONSUMED`

Each approval references an immutable, canonicalized, versioned proposal snapshot and proposal hash. Approval commands require authenticated authorization, CSRF for browser sessions, ETag/expected version, proposal hash, and selective command idempotency.

Single-action approvals bind to at most one durable tool execution. State-changing execution uses a separate stable execution idempotency identity. If the external effect is uncertain, the approval remains bound and the execution enters reconciliation.

## Alternatives Considered

- Boolean approval.
- Approval represented only by workflow status.
- Approval ID without version or proposal-hash preconditions.
- Approval embedded directly in tool execution.

## Rationale

This design separates user authorization from operational execution and protects against stale proposals, changed arguments, duplicate submissions, and replay.

## Positive Consequences

- Exact user-reviewed action is auditable.
- Multiple approval points per workflow are supported.
- Approval infrastructure is reusable across workflows.
- Rejection and expiration are explicit.
- Changed proposals require renewed review.
- Uncertain effects cannot consume a fresh approval accidentally.

## Negative Consequences

- More states and validation rules.
- Canonicalization and proposal hashing require careful versioning.
- Clients must preserve ETags and proposal hashes.
- Approval and execution cannot be one atomic transaction across an external system.

## Implementation Guardrails

- A material proposal change supersedes the original approval.
- A rejected, expired, superseded, cancelled, or consumed approval cannot authorize execution.
- Approval does not bypass current authorization or source access checks.
- External execution occurs outside the database transaction.
- Rejection produces no external side effect.
- Defined-scope approval applies only to its displayed workflow run and limits.

## Revisit When

- Multi-party, delegated, or voting approvals become requirements.
- Approval policy must vary by role, risk, or organization.
- External systems provide transactional action reservation that changes binding semantics.

---

# ADR-008: Hybrid Retrieval with Reciprocal Rank Fusion and Optional Evaluated Reranking

## Status

Accepted

## Context

Research sources include prose, documentation, code, configuration, identifiers, error messages, filenames, and exact technical terms. Vector-only retrieval performs poorly for some exact-match needs. Lexical-only retrieval misses conceptual similarity. A dedicated external search platform would add infrastructure before representative scale exists.

## Decision

Implement a provider-neutral Knowledge and Retrieval pipeline using:

1. Authorization and source-scope filtering.
2. Query normalization.
3. PostgreSQL lexical retrieval.
4. pgvector semantic retrieval.
5. Reciprocal Rank Fusion.
6. Deduplication and overlap reduction.
7. Relevance thresholds.
8. Optional reranking only after baseline evaluation demonstrates sufficient benefit.

Version the segment, embedding, and retrieval generations. Activate complete generations atomically and preserve prior active generations until replacement succeeds.

## Alternatives Considered

- Vector retrieval for all content.
- Fixed weighted lexical/vector score merging.
- Reciprocal Rank Fusion without a reranker extension point.
- Dedicated search engine or vector database.

## Rationale

Hybrid retrieval supports both exact and conceptual search while RRF avoids comparing incompatible raw score scales. Progressive reranking avoids adding cost before evidence demonstrates value.

## Positive Consequences

- Better fit for mixed technical content.
- PostgreSQL remains sufficient for the MVP.
- Retrieval strategies can evolve behind one contract.
- Historical runs can identify the retrieval profile used.
- Failed re-indexing does not replace the active generation.

## Negative Consequences

- More evaluation and index metadata than vector-only retrieval.
- RRF constants and thresholds require tuning.
- pgvector physical design depends on selected embedding dimensions and corpus size.
- Optional reranking adds latency and provider cost if enabled.

## Implementation Guardrails

- Authorization is enforced before candidates are returned.
- Retrieval returns evidence candidates, not final answers.
- The pipeline may return no sufficiently relevant evidence.
- Citation support is validated separately from retrieval rank.
- New model dimensions create a compatible new generation rather than mutating existing vectors.
- A dedicated search system requires measured justification.

## Revisit When

- Representative evaluation shows insufficient retrieval quality.
- Corpus scale makes PostgreSQL search or filtering inadequate.
- Reranking provides a measured quality benefit worth its latency and cost.
- New source types require specialized retrieval strategies.

---

# ADR-009: Platform Tool Gateway with Native and MCP Adapters

## Status

Accepted

## Context

The product must support future research and non-research tools. Some capabilities are easiest as trusted native application tools; others may be exposed by MCP servers. Making every tool MCP-only would add unnecessary protocol boundaries. Native-only tools would limit interoperability and the intended AI-engineering learning goals.

Workflows must not independently implement validation, approvals, timeouts, persistence, idempotency, error normalization, and credential policy.

## Decision

Define one platform-owned normalized tool contract and Tool Gateway.

The Gateway owns:

- Tool resolution and availability.
- Workflow permission.
- Input and output validation.
- Effect classification.
- Approval enforcement.
- Budgets and timeouts.
- Durable execution identity and records.
- Idempotency and reconciliation policy.
- Result and failure normalization.

Adapters implement native tools, MCP tools, and future protocols. MCP metadata cannot weaken platform policy.

Tools declare one invocation mode:

- `WORKFLOW_ONLY`
- `DIRECT_ALLOWED`
- `INTERNAL_ONLY`

Workflow mediation is the default. Only explicitly permitted tools are directly callable by users.

## Alternatives Considered

- MCP-only tools.
- Native internal tools only.
- Direct workflow-to-tool calls.
- Expose every discovered tool directly.
- Tools available only through workflows.

## Rationale

A platform-owned contract gives workflows one consistent interface, preserves simple native tools, permits MCP interoperability, and centralizes policy without accumulating tool-specific protocol logic in the Gateway.

## Positive Consequences

- Native and MCP tools behave consistently to workflows.
- Approval, audit, and idempotency are reusable.
- Additional adapters are localized.
- Internal tools remain hidden.
- One non-research direct tool can prove extension boundaries.

## Negative Consequences

- Normalization may not represent every provider-specific feature.
- MCP schema and availability changes require compatibility handling.
- Tool definitions and adapters need contract tests.
- A remote MCP server adds another trust and failure boundary.

## Implementation Guardrails

- MCP servers are operator-configured and trusted in the MVP.
- MCP tools receive only scoped credentials and inputs.
- State-changing tools always follow approval policy.
- Tool discovery does not imply invocation permission.
- Large results use content storage rather than unbounded JSONB.
- Tool-specific logic remains in adapters, not in the central Gateway.

## Revisit When

- Untrusted plugin installation becomes a product requirement.
- Tool isolation requires separate processes or sandboxes.
- MCP becomes sufficiently universal to justify a different default.
- Tool-catalog scale requires its own deployable service.

---

# ADR-010: Separate Conversation, Workflow, Workspace-Knowledge, and User-Memory Contexts

## Status

Accepted

## Context

The product needs continuity, but conversation history, runtime workflow state, source knowledge, generated outputs, explicit decisions, and user preferences have different authority, retention, and security semantics. Treating them as one semantic memory would mix source evidence, model-generated content, user intent, and operational state.

## Decision

Separate:

1. Conversation context: conversations, messages, typed message parts, and derived summaries.
2. Workflow state: structured lifecycle, segments, approvals, tools, jobs, and checkpoints.
3. Workspace knowledge: sources, versions, normalized content, retrieval segments, findings, evidence, and artifacts.
4. User memory: explicit preferences and deliberately saved cross-workspace settings.
5. Workspace decisions: append-only accepted decisions with active, superseded, withdrawn, and draft states.

Use stage-specific Context Assembly to include the minimum authorized context required by each model call. Summaries are derived and never authoritative. Only active workspace decisions are used as current direction by default.

## Alternatives Considered

- Conversation history as the primary memory store.
- Unified semantic memory for all retained information.
- Conversation summaries as the main context source.
- LangGraph Store as authoritative long-term memory.

## Rationale

Explicit separation improves authority, deletion, provenance, context budgeting, prompt-injection resistance, and compatibility with non-conversational workflows.

## Positive Consequences

- Workflow state is not reconstructed from chat.
- Generated recommendations do not become user decisions automatically.
- Context sent to providers is smaller and better governed.
- Superseded decisions remain historical but cease to direct current work.
- Future workflows choose relevant context categories.

## Negative Consequences

- More data entities and context-selection policy.
- Summaries, decisions, findings, and messages may reference related concepts.
- Context omission risk must be evaluated.
- User interaction is needed to save explicit preferences or decisions.

## Implementation Guardrails

- Context authority order is platform policy, current user request, workflow facts, conversation, then untrusted evidence and tool observations.
- Summaries reference their source messages and become stale when those sources change.
- One active decision exists per workspace and decision key.
- Superseding a decision creates a new record rather than editing history.
- Generated content is not promoted to source evidence merely because it is indexed.
- Global user preferences are not inferred and stored without explicit action.

## Revisit When

- Cross-workspace semantic memory becomes an explicit product goal.
- Users need automatic preference learning with suitable consent and controls.
- Context evaluation demonstrates that the current categories are insufficient.

---

# ADR-011: PostgreSQL Data Organization, Versioning, Retention, and Staged Deletion

## Status

Accepted

## Context

The application stores identity, conversations, workflows, approvals, sources, multiple source versions, retrieval generations, findings, artifacts, events, provider calls, and large storage references. It must preserve historical provenance, support extension-specific payloads, prevent orphaned relationships, and delete data safely across PostgreSQL, checkpoint tables, embeddings, and file/object storage.

## Decision

Use five bounded PostgreSQL schemas:

- `iam`
- `workspace`
- `execution`
- `knowledge`
- `content`

Use:

- UUIDv7 for durable externally referenced entities.
- Cross-schema foreign keys for integrity.
- Application-enforced module mutation ownership.
- Relational core fields for lifecycle, authorization, identity, constraints, queries, and reporting.
- Bounded, typed, versioned JSONB for workflow-, tool-, event-, and provider-specific payloads.
- Logical sources with immutable content versions, processing runs, normalized blocks, and retrieval segments.
- Logical artifacts with immutable versions, stored objects, relationships, and external exports.
- First-class findings, evidence links, and artifact placements.
- Separate outbox events, dispatcher-created handler deliveries, and progress events.
- Access-pattern-driven indexes with measured refinement.
- Text statuses with database checks and domain state machines.
- Expand, migrate, and contract schema evolution.
- Staged deletion with retention classes and idempotent asynchronous purge.

## Alternatives Considered

- One public schema.
- One schema per logical module.
- Strict schema isolation without cross-schema foreign keys.
- Mostly relational or mostly JSONB storage.
- Mutable source and artifact records.
- Immediate hard deletion.
- Indefinite soft deletion.
- Broad indexing or primary-key-only indexing.
- PostgreSQL enum types for all statuses.
- Destructive one-release migrations.

## Rationale

This model preserves strong relational integrity and historical provenance while keeping extension-specific details flexible. It avoids both an unstructured document-store design and excessive schema fragmentation.

## Positive Consequences

- Durable sources, findings, artifacts, decisions, and approvals remain auditable.
- Conforming workflows and tools often use shared entities without migrations.
- Genuinely new domain concepts can add dedicated relational structures.
- Historical citations remain tied to immutable source versions.
- Cleanup can coordinate shared stored objects and derived indexes safely.
- Schema changes remain compatible with durable waiting workflows.

## Negative Consequences

- The data model is substantial.
- Cross-schema migrations and cleanup ordering require discipline.
- JSONB payload readers need compatibility support.
- Version and generation management adds metadata.
- Staged deletion retains data temporarily and requires cleanup workflows.

## Implementation Guardrails

- No generic unbounded `data` or `state` JSONB dumping ground.
- Promote JSONB properties when they become lifecycle-, authorization-, or query-significant.
- Do not cascade-delete complete workspace graphs.
- Physical objects are removed only after retained references are gone.
- New source, segment, embedding, and artifact versions activate only after successful validation.
- Database and runtime compatibility ranges are checked at readiness.
- Unknown payload versions fail safely.

## Revisit When

- Data volume or tenancy requires partitioning or separate databases.
- A module becomes an independently deployed service.
- PostgreSQL vector/search performance becomes inadequate.
- Regulatory retention or deletion requirements become formal product constraints.

---

# ADR-012: Deployment-Specific Identity, Storage, Secrets, Observability, and Provider Adapters

## Status

Accepted

## Context

The product must run locally and remotely without hard-coding one cloud provider. Local use should remain simple, while remote deployments require authentication and production-appropriate secrets, storage, health, and observability. The MVP should implement one provider per capability without leaking provider SDKs into workflows.

## Decision

### Identity

- Use an internal user identity for ownership.
- Map external identities separately.
- Use a synthetic `LOCAL_TRUSTED` external identity in explicitly safe local mode.
- Require OIDC for remote deployment.
- Use opaque server-side application sessions.
- Fail closed rather than falling back from broken remote OIDC to local trusted mode.

### Storage

- Use a platform content-storage contract.
- Implement local filesystem storage first.
- Permit object-storage adapters later.
- Keep storage keys and paths private from public contracts.

### Secrets and Configuration

- Use a configuration abstraction with deployment-specific secret sources.
- Support ignored local secret files or environment variables for development.
- Support mounted secret files or managed secret services remotely.
- Never store secret values in provider configuration, logs, traces, prompts, artifacts, or ordinary state.

### Providers

- Define capability-specific ports for generation, structured generation, embeddings, web search, webpage retrieval, and optional reranking.
- Implement one provider per required capability for the MVP.
- Normalize requests, results, usage, refusals, and failures.
- Do not automatically fall back across providers.

### Observability

- Emit OpenTelemetry-compatible logs, metrics, and traces incrementally.
- Correlate browser requests, workspaces, runs, jobs, segments, providers, tools, approvals, and artifacts.
- Exclude raw prompts, full responses, source content, credentials, and sensitive tool arguments by default.

### Deployment Health and Limits

- Separate liveness, readiness, and authenticated capability status.
- Apply layered deployment, user, endpoint-class, upload, SSE, and workflow-budget controls.
- Use one application image with web and worker roles.

## Alternatives Considered

- Application-managed passwords.
- OIDC-only authentication for local and remote modes.
- Browser-managed provider access tokens.
- Local filesystem paths embedded directly in domain records.
- Cloud secret manager required everywhere.
- Environment variables read throughout the codebase.
- Thin provider SDK wrappers.
- One universal provider interface.
- Logging only.
- Automatic provider fallback.

## Rationale

Deployment-specific adapters keep local development lightweight while preserving secure remote operation and future cloud portability. Capability-specific provider ports and vendor-neutral telemetry prevent infrastructure choices from dominating workflow logic.

## Positive Consequences

- Local and remote modes share internal user and authorization semantics.
- External identity-provider replacement does not rewrite workspace ownership.
- Storage and providers remain replaceable.
- One-provider MVP remains feasible.
- Remote deployments have an explicit secure authentication path.
- Telemetry provides a production-quality operating story without one vendor dependency.

## Negative Consequences

- Several adapter contracts must be tested.
- Remote deployment requires OIDC configuration.
- Local trusted mode requires strict safety checks.
- Server-side sessions require persistence and cleanup.
- Telemetry backends and cloud object storage remain deployment work.

## Implementation Guardrails

- OIDC authentication tokens are not reused automatically as tool credentials.
- Web and worker roles receive only the credentials they require.
- Optional capability failure disables that capability rather than crashing unrelated features when safe.
- Health endpoints reveal minimal public information.
- Capability status and remediation details require authentication.
- Provider SDK retries are bounded and observable.
- More infrastructure is added only when a requirement or measurement justifies it.

## Revisit When

- Machine authentication becomes a product requirement.
- Multi-user or enterprise identity requirements expand.
- A cloud reference deployment is selected.
- Provider portability requires more than one implemented adapter.
- Observability scale or compliance requires a specific backend.

---

# Cross-ADR Consistency Summary

The twelve decisions form one coherent architecture:

1. The modular monolith establishes a manageable application boundary.
2. PostgreSQL provides authoritative state and durable coordination.
3. HTMX, JSON, and SSE provide a lean but extensible user and integration surface.
4. Controlled workflows bound model discretion.
5. The platform owns business lifecycle while LangGraph owns continuation checkpoints.
6. Durable segments, leases, idempotency, and reconciliation provide honest recovery semantics.
7. First-class approvals protect state-changing actions.
8. Hybrid retrieval and evidence validation support source-traceable briefings.
9. The Tool Gateway supports native, MCP, research, and non-research capabilities.
10. Explicit context categories prevent conversation, evidence, workflow state, and user memory from being conflated.
11. Versioned PostgreSQL data and staged deletion preserve integrity and provenance.
12. Deployment adapters preserve local simplicity and remote security without forcing one provider or cloud.

No accepted ADR conflicts with the PRD, HLA, TDD, Data Design Document, or API Contract.

# ADR Maintenance Policy

- New consequential decisions are appended with the next ADR number.
- Accepted records are not silently rewritten when the decision changes.
- A replaced decision is marked `Superseded` and links to its successor.
- Clarifications that do not change the decision may be added with a dated amendment note.
- Implementation-only choices do not require ADRs unless they create important long-term constraints, cross-cutting consequences, or difficult reversibility.
- The consolidated document remains the authoritative ADR record for the initial project.

# Implementation Readiness

The architecture discovery set is complete:

- Product Requirements Document
- High-Level Architecture
- Technical Design Document
- Data Design Document
- API Contract
- Consolidated Architecture Decision Records

Implementation can begin without another mandatory architecture document. Delivery artifacts such as the backlog, threat-model checklist, evaluation dataset, deployment guide, and README should evolve alongside the code rather than delay the first vertical slice.
