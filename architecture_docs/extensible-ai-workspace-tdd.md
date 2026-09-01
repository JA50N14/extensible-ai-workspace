# Technical Design Document: Extensible AI Workspace

## 1. Document Control

| Field | Value |
|---|---|
| Document | Technical Design Document (TDD) |
| Product | Extensible AI Workspace |
| Version | 1.0 |
| Status | Approved baseline for data and API design |
| Owner | Jason MacFarlane |
| Inputs | Product Requirements Document v1.0; High-Level Architecture v1.0 |

## 2. Purpose and Scope

This document defines how the approved high-level architecture will behave internally. It covers module layering, cross-module communication, durable workflow execution, approvals, tools, ingestion, retrieval, context assembly, provider integration, streaming, security mechanics, failure handling, observability, and testing.

It intentionally does not finalize relational tables, indexes, retention rules, endpoint payloads, repository structure, prompt text, chunk sizes, model names, or cloud-provider services. Those belong in later documents or implementation-time configuration.

## 3. Design Principles

1. Platform state remains authoritative independently of LangGraph or another workflow runtime.
2. Workflow-specific modules depend on generic platform capabilities; generic modules do not depend on Research-to-Briefing.
3. Business invariants remain separate from FastAPI, PostgreSQL, LangGraph, MCP, storage, and provider SDKs.
4. External operations occur outside long-running database transactions.
5. Durable work is processed at least once, with idempotency and reconciliation safeguards.
6. Source content, model output, and tool output are untrusted data rather than authorized instructions.
7. The application persists meaningful state and progress, not every transient token or runtime detail.
8. Extension contracts are practical and bounded; the platform does not become a no-code builder.
9. One complete, evaluable vertical slice takes priority over broad provider or workflow coverage.

## 4. Module Internal Architecture

The modular monolith uses pragmatic ports and adapters where a meaningful business or infrastructure boundary exists.

### 4.1 Domain

The domain layer owns business concepts, state-transition rules, and invariants. It does not depend on FastAPI, SQLAlchemy, LangGraph, MCP, provider SDKs, or cloud services.

Examples include:

- An expired approval cannot authorize execution.
- A consumed approval cannot be replayed.
- A completed workflow cannot transition back to running.
- A revoked folder permission cannot authorize a new read.
- An existing artifact cannot be overwritten unless the approval covered that overwrite.

### 4.2 Application

The application layer implements use cases and coordinates domain operations. A use case has a trigger, inputs, authorization requirements, business rules, dependencies, success result, and failure outcomes.

Examples include:

- Create workspace
- Start workflow
- Record approval
- Cancel workflow
- Register source
- Execute an approved tool
- Create artifact package

The application layer determines operation order and transaction boundaries but delegates domain validity, persistence, and provider work to the appropriate contracts.

### 4.3 Ports

Ports describe capabilities required by application logic without naming the technology that supplies them. Ports are introduced only for meaningful boundaries.

Examples include:

- Repository access
- Unit of Work
- Content storage
- Model inference
- Embedding generation
- Web search
- Webpage retrieval
- Tool execution
- Identity validation
- Workflow checkpoint persistence
- Progress publication
- Clock and secrets

### 4.4 Adapters

Adapters implement ports using specific technologies or protocols. Examples include PostgreSQL repositories, local filesystem storage, object storage, OIDC, native tools, MCP, model providers, web search, and OpenTelemetry.

Adapters translate technology-specific requests, responses, exceptions, authentication, timeouts, and serialization into internal contracts.

### 4.5 Presentation

Presentation includes FastAPI routes, HTMX handlers, SSE endpoints, form parsing, view-model construction, and safe response translation. Presentation calls application use cases and does not own business rules, SQL, provider calls, or approval policy.

### 4.6 Dependency Direction

```text
Presentation  ---------------->  Application
                                   |
                                   | applies
                                   v
                                Domain

Application  ---- depends on ----> Ports
                                   ^
                                   |
                    implements     |
Adapters  -------------------------+
```

Not every module requires every physical layer. The pattern is applied where it protects rules or external boundaries rather than to create empty abstractions.

## 5. Cross-Module Communication

### 5.1 Synchronous Application Contracts

Use synchronous internal contracts when an immediate result is required before proceeding, such as authorization, cancellation eligibility, source availability, or artifact lookup.

A module must not directly modify another module's tables or import its ORM entities. Cross-module queries return purpose-built read models or application results.

### 5.2 Durable Post-Commit Events

Use durable application events when another module reacts after a committed state change and the reaction can retry independently.

Examples include:

- `WorkflowStarted`
- `ApprovalRecorded`
- `SourceRegistered`
- `ToolExecutionCompleted`
- `ArtifactCreated`
- `WorkflowCompleted`

Events describe facts that have occurred. They carry stable identifiers and a small versioned payload rather than entire domain objects or sensitive content.

### 5.3 Transactional Outbox

The business change and its outbox event are written in the same PostgreSQL transaction. A dispatcher later claims and delivers committed events to registered handlers. This prevents a committed state change from losing its required follow-up reaction.

Delivery is at least once. Handlers must be idempotent and delivery attempts must be recorded. PostgreSQL is sufficient for the MVP; no broker is required.

Outbox events and executable jobs remain distinct. An event announces a committed fact; a handler may create a job representing eligible work.

## 6. Transaction Management

Use explicit short transactions per application use case or durable workflow boundary.

Repositories participate in an application-controlled Unit of Work and do not commit independently.

External operations are never performed while holding a long-running database transaction. The standard sequence is:

1. Persist intention and execution identity.
2. Commit.
3. Perform the external operation.
4. Begin a new transaction.
5. Record result and next state.
6. Reconcile if the external operation completed but its result could not be persisted.

PostgreSQL and content storage do not share a transaction. Stored content is prepared under a stable identity, verified, associated with committed metadata, and exposed as complete only after platform state recognizes it. Abandoned temporary objects are cleaned later.

Concurrency controls may include row locks, optimistic concurrency, state predicates, unique idempotency constraints, and safe transaction retries. Exact schema and SQL are deferred to the Data Design Document.

## 7. Platform and Runtime Workflow State

### 7.1 Platform-Owned State

The platform owns authoritative:

- Workflow identity and version
- User and workspace ownership
- Common lifecycle status
- User-visible stage and progress
- Pending input or approval
- Cancellation and recovery state
- Completion result and failure category
- Job eligibility
- Artifacts and tool-execution references
- Timestamps and audit relationships

### 7.2 Runtime-Owned Checkpoints

LangGraph or another runtime may durably persist workflow-run-scoped continuation state:

- Current graph position
- Conditional branch state
- Bounded agentic iteration
- Temporary intermediate values
- Information required to resume after interruption

Checkpoints normally contain stable references rather than copies of documents, conversations, approvals, artifacts, or tool history.

LangGraph may execute nodes, edges, conditional edges, interruptions, and resumptions. Its cross-thread Store is not the authoritative application memory layer.

### 7.3 Workflow Versioning

Every run retains its workflow type and version. Compatible checkpoints resume normally; known formats may be migrated; incompatible checkpoints enter a clear recovery state. Completed runs remain readable even if their executable version is no longer active.

The worker must never restart an incompatible or missing checkpoint from the beginning when doing so might repeat external effects.

## 8. Durable Job Coordination

### 8.1 Claiming

Workers claim eligible jobs in a short PostgreSQL transaction using `FOR UPDATE SKIP LOCKED`. The worker writes:

- Worker identifier
- Lease identifier
- Lease expiry
- Attempt number
- Claim timestamp
- Running status

The transaction commits before external work begins.

### 8.2 Renewable Leases

The worker renews its lease during active work. Other workers skip jobs with valid leases. Expired leases make jobs eligible for recovery, not blind restart.

Before committing a result, a worker verifies it still owns the active lease. A stale worker cannot overwrite a recovery worker's state.

### 8.3 Recovery

Recovery inspects platform lifecycle, runtime checkpoint, cancellation status, approval state, completed stages, tool executions, idempotency records, and uncertain effects. It resumes from durable state rather than from the workflow beginning.

### 8.4 Pauses

A worker never holds a lease while waiting for human input or approval. It persists the checkpoint and waiting state, completes the current job, and creates new eligible work only after the decision commits.

## 9. Durable Execution Segments

One durable job executes one meaningful workflow segment. A segment may contain several LangGraph nodes and ends at a recovery, retry, approval, cancellation, long-operation, state-changing-tool, completion, or budget boundary.

User-visible stages, runtime graph nodes, and durable job segments remain distinct concepts.

A successful segment completion:

1. Confirms lease ownership.
2. Persists domain outputs through owning modules.
3. Saves the runtime checkpoint.
4. Updates workflow lifecycle and progress.
5. Records tool and provider outcomes.
6. Writes required outbox events.
7. Creates continuation work when eligible.
8. Completes the current job.
9. Commits the short transaction.

A state-changing tool invocation is normally isolated in its own segment after a durable approval pause.

Each segment has configurable budgets for time, model calls, tool calls, agentic iterations, retrieved webpages, candidate evidence, and retry attempts. Exhaustion preserves work and yields a limitation, continuation, scope adjustment, or normalized failure rather than extending the budget silently.

## 10. Approval Design

Approvals are first-class records independent of workflow status.

### 10.1 States

- `PENDING`
- `APPROVED`
- `REJECTED`
- `EXPIRED`
- `SUPERSEDED`
- `CANCELLED`
- `CONSUMED`

### 10.2 Immutable Proposal

An approval references an immutable canonical action snapshot containing the tool or authorization type, version, effect classification, target, validated arguments, expected effect, affected resources, workflow context, user-readable summary, proposal hash, creation time, and optional expiry.

A material proposal change supersedes the existing approval and creates a new pending request.

### 10.3 Execution Binding

A state-changing tool execution uniquely claims an approved action. A unique constraint prevents another execution from using the same approval. After a definitive result, the approval becomes consumed. If the result is uncertain, the approval remains bound and cannot be reused until reconciliation.

Approval validity checks include state, expiry, proposal hash, tool identity, arguments, authorization, workspace, workflow state, and prior binding.

### 10.4 Approval Semantics

Supported semantics include:

- Single exact action
- Defined workflow scope, such as approved web research for one run

Approval identity, decision, approver, and timestamps remain independently auditable.

## 11. Tool Gateway

Workflows invoke native and MCP tools through one platform Tool Gateway.

### 11.1 Gateway Responsibilities

- Resolve stable tool identity and version
- Confirm availability and workflow permission
- Validate normalized input
- Enforce deployment and workflow budgets
- Determine approval requirements
- Validate exact-action approval
- Create durable execution identity
- Select the adapter
- Normalize result or failure
- Record usage, result, idempotency, and reconciliation state

### 11.2 Adapter Responsibilities

- Translate normalized input
- Use only specifically assigned credentials
- Invoke native code or MCP
- Apply protocol timeout and cancellation
- Translate output and errors
- Return provider-specific diagnostics only through protected metadata

### 11.3 Tool Contract

A normalized tool declares:

- Stable identifier and version
- Name and purpose
- Input and result schemas
- Read-only or state-changing effect
- Approval policy
- Required configuration and credentials
- Timeout and cancellation support
- Error categories
- Origin and availability
- Idempotency capability

External MCP metadata cannot weaken platform policy. MCP servers are explicitly configured and trusted for the MVP, while the platform may impose stricter classifications.

## 12. Content-Processing Pipeline

Use format-specific extractors that produce one normalized content model.

### 12.1 Pipeline

1. Register source and origin.
2. Validate authorization, format, signature, size, availability, and checksum.
3. Acquire content safely through approved storage or source ports.
4. Extract content using a format adapter.
5. Normalize structure and location metadata.
6. Segment into retrieval units.
7. Submit segments to Knowledge and Retrieval.
8. Record success, warnings, partial processing, unsupported format, stale content, failure, unavailability, or revocation.

### 12.2 Normalized Content

The representation preserves:

- Source and source-version identifiers
- Content type, title, and filename
- Ordered structural blocks
- Heading hierarchy
- Page numbers where available
- Line ranges where meaningful
- Links and URL locations
- Code language and path where relevant
- Extraction warnings
- Parser identity and version
- Checksum and extraction time

### 12.3 Safe Local Access

Before each read, local-source acquisition revalidates active approval, path containment, recursion scope, symbolic links, traversal protection, availability, and expected content version.

### 12.4 Versioning and Duplicates

Logical sources retain independently identifiable content versions. A new version becomes current only after required processing succeeds. Historical citations retain their original version.

Exact duplicate work may be reused, but separate source identities and provenance remain intact.

### 12.5 MVP Formats

- Text PDF without OCR
- DOCX textual structure
- Markdown
- TXT
- HTML
- Common source-code and configuration text

OCR, images, audio, video, spreadsheets, presentations, exact layout preservation, and universal syntax trees are deferred.

## 13. Hybrid Retrieval

The retrieval pipeline uses:

1. Authorization and source-scope filtering
2. Query normalization
3. PostgreSQL lexical retrieval
4. pgvector semantic retrieval
5. Reciprocal Rank Fusion
6. Candidate deduplication and overlap reduction
7. Optional reranking after baseline evaluation
8. Relevance thresholding
9. Evidence candidates with provenance

Authorization is applied before retrieval, not after searching all indexed content.

RRF combines ranks rather than incompatible lexical and vector score scales. Reranking is behind a capability contract and is not required for the initial vertical slice.

The pipeline may return no sufficiently relevant evidence. The workflow then clarifies, proposes web research, continues with limitations, or reports insufficiency.

Each candidate includes source/version identity, provenance, location, secure text or reference, retrieval signals, fused rank, optional reranker result, checksum, timestamp, availability, and relevant processing warnings.

Retrieval relevance does not prove citation support. The Research workflow separately validates whether a passage supports its attached claim.

## 14. Context Assembly

Each workflow stage declares the context categories it needs. A shared Context Assembly service gathers the minimum authorized information within a configured token budget.

### 14.1 Context Categories

- Platform and stage instructions
- Current user instruction
- Structured workflow facts
- Relevant conversation context
- Retrieved source evidence
- Required tool results
- Explicit user preferences

### 14.2 Authority Order

```text
Platform policy and stage instructions
        ↓
Current authorized user request
        ↓
Structured workflow facts
        ↓
Conversation context
        ↓
Untrusted evidence and tool observations
```

Lower-authority content cannot approve actions, expand access, reveal credentials, change budgets, or override policy.

### 14.3 Conversation Summaries

Summaries are derived optimizations rather than authoritative memory. They reference their source messages, are versioned, preserve accepted decisions separately, never replace original messages, and lose to structured platform state when inconsistent.

### 14.4 Budgeting and Overflow

The assembler reserves output capacity, includes mandatory policy and current input, includes required facts, adds ranked evidence and tool results, and then adds relevant conversation and preferences. Duplicate evidence is removed before essential material is truncated.

If context remains too large, the workflow summarizes lower-priority conversation, processes evidence in batches, narrows scope, or reports a limitation. It does not silently drop mandatory policy or switch to a more expensive provider without authorization.

### 14.5 Provenance Metadata

Each model invocation records context-policy version, included record identifiers, token counts by category, exclusion counts and reasons, and provider/model configuration identifiers. Raw context is excluded from normal telemetry.

## 15. Provider Adapters

Use capability-specific ports for:

- Text generation
- Structured generation
- Embeddings
- Web search
- Webpage retrieval
- Optional reranking

Adapters implement only supported capabilities and declare capability metadata. Startup and workflow validation fail early when required capabilities are unavailable.

Adapters normalize requests, results, finish reasons, usage, request identifiers, refusals, timeouts, rate limits, malformed responses, and failures.

The platform owns retry policy. Hidden SDK retries are disabled or bounded and included in accounting.

Stream adapters translate provider chunks into normalized output events. Partial streamed text is not a completed output. Final structured results are validated against internal schemas, with bounded repair attempts when policy permits.

Automatic cross-provider fallback is outside the MVP because privacy, capability, cost, and consent may differ.

## 16. Progress and SSE Delivery

Workers persist meaningful progress events and batched accumulated-output snapshots. Web runtimes deliver them through authenticated SSE, with polling fallback.

A progress event includes workflow-run identity, per-run sequence, type, user-visible stage, timestamp, versioned payload, correlation identity, and optional related job, tool, approval, or artifact identity.

Durable events include lifecycle and stage transitions, approval requirements, tool outcomes, failures, cancellation, artifact availability, completion, and periodic output snapshots. Individual tokens, repeated status, heartbeats, and private model reasoning are not persisted as progress records.

The browser reconnects using its last sequence. The server reauthorizes the run and sends retained later events. If the cursor has expired, it sends a current-state snapshot and resumes from the current sequence.

`LISTEN/NOTIFY` may later reduce detection delay, but durable PostgreSQL records remain authoritative.

Transactional-outbox events drive post-commit application reactions; workflow-progress events support the UI and durable execution history. They remain separate concepts.

## 17. Authentication, Sessions, CSRF, and Authorization

### 17.1 Remote Authentication

Remote deployments use OIDC login and then create an opaque server-side application session. Provider tokens are not stored in browser-accessible state.

PostgreSQL initially stores session identity, internal user, creation, activity, absolute and idle expiry, authentication method, provider subject, revocation, and security metadata.

The browser cookie is opaque and uses secure production attributes, including `Secure`, `HttpOnly`, appropriate `SameSite`, and restricted scope. Sessions rotate after sensitive transitions.

### 17.2 Local Trusted Mode

Local mode resolves one configured internal user without OIDC. It must be explicitly selected and compatible with trusted local binding. Unsafe combinations fail startup. A failed remote identity configuration never falls back silently to local mode.

### 17.3 CSRF

All state-changing browser requests use non-GET methods and validate a session-bound CSRF token. Origin validation may provide additional protection. HTMX headers are not treated as proof of authenticity.

### 17.4 Authorization

Explicit action policies include workspace, source, workflow, approval, artifact, tool, and configuration operations. The MVP normally resolves authorization through resource ownership, but policy names remain explicit for future evolution.

Presentation may perform an early check; the application use case performs the authoritative check. Workers revalidate applicable permissions, source access, approval, and cancellation before consequential execution.

OIDC authentication tokens are not automatically reused as delegated tool credentials. Tool authorization is separately configured and scoped.

## 18. Shared Failure Model

Modules interpret their own failures and map them into shared platform categories:

- Validation
- Authentication
- Authorization
- Configuration
- Unsupported capability
- Resource limit
- Transient dependency
- Rate limit
- Permanent source or dependency
- Tool-declared business failure
- Structured-output validation
- Cancellation
- Uncertain external outcome
- Data-integrity failure
- Application defect

A normalized failure includes stable code, category, user-safe message, protected diagnostic message, retry classification, affected operation, correlation identity, related resource identifiers, partial-result availability, and suggested user action when known.

Retry classes are:

- Never retry automatically
- Bounded automatic retry
- Retry after user or configuration correction
- Reconcile before retry
- Continue with limitations
- Cancel cleanly

## 19. Startup, Health, and Capability Validation

### 19.1 Web Runtime

Before readiness, validate deployment mode, remote OIDC, session security, PostgreSQL, schema compatibility, content storage, required secrets, and local-mode safety.

### 19.2 Worker Runtime

Validate PostgreSQL, schema, checkpoint persistence, content storage, providers, native tools, configured MCP availability, workflow registration, and resource budgets.

Essential dependency failure prevents readiness. Optional capability failure marks only affected tools or workflows unavailable and exposes the reason safely.

Liveness reports whether the process responds. Readiness reports whether the runtime can safely perform its assigned role. Individual capability availability is reported separately.

## 20. Observability

OpenTelemetry-compatible instrumentation is added incrementally at:

- HTTP requests
- Application use cases
- Database transactions
- Outbox delivery
- Job claims and segments
- Workflow stages
- Extraction and retrieval
- Provider calls
- Tool executions
- Approval transitions
- Artifact operations

Correlation connects HTTP request, workspace, run, job, segment, provider/tool call, approval, and artifact where appropriate.

Telemetry records operational metadata rather than raw prompts, model responses, document text, retrieved passages, credentials, or sensitive tool arguments by default. Instrumentation avoids token-level spans and trivial helper spans.

## 21. Testing Strategy

### 21.1 Domain Tests

Test invariants and transitions without infrastructure, including approvals, lifecycle, budgets, cancellation, effect classification, and overwrite protection.

### 21.2 Application Use-Case Tests

Use deterministic fake ports to test orchestration, transactions, authorization, partial completion, and normalized failures.

### 21.3 Adapter Contract Tests

Verify storage, provider, tool, identity, repository, MCP, and checkpoint adapters against their internal port contracts.

### 21.4 PostgreSQL Integration Tests

Use real PostgreSQL for locking, leases, outbox atomicity, unique idempotency, optimistic concurrency, rollback, sessions, lexical retrieval, pgvector, and migrations. SQLite is not an adequate substitute for these behaviours.

### 21.5 Workflow Tests

Use deterministic fake providers and tools for successful, approved, rejected, declined, cancelled, partial, rate-limited, crash-recovery, uncertain-effect, budget-exhausted, and incompatible-checkpoint paths.

### 21.6 AI Evaluation

Maintain a versioned evaluation set for retrieval relevance, citation support, unsupported claims, conflicts, prompt injection, structured output, evidence classification, and briefing completeness. Evaluation metrics remain separate from deterministic test pass/fail results.

### 21.7 Security Tests

Cover cross-workspace access, CSRF, approval replay and mutation, expiry, path traversal, symlink escape, secret redaction, source injection, unsafe authentication startup, and MCP scope violations.

### 21.8 End-to-End Smoke Tests

Verify authentication/local mode, workspace creation, source addition, workflow execution, progress delivery, briefing review, approved artifact creation, and durable reopen.

### 21.9 Live Provider Tests

Live model, web, OIDC, and MCP tests are isolated, explicitly enabled, and excluded from the normal deterministic suite because they may be billed, slow, variable, or unavailable.

## 22. Principal Technical Sequences

### 22.1 Start Workflow

1. Authenticate and authorize user.
2. Validate workflow type, inputs, capabilities, source scope, and budgets.
3. In one transaction, create workflow run, initial state, executable job, progress record, and outbox events.
4. Commit and return run identity and initial view.
5. Worker claims the job using `SKIP LOCKED` and a lease.

### 22.2 Record Approval

1. Authenticate request and validate CSRF.
2. Authorize user for workspace and approval.
3. Load immutable proposal and current approval state.
4. Apply domain transition.
5. In one transaction, record decision, progress, and outbox event.
6. Dispatcher delivers event idempotently.
7. Workflow module creates eligible continuation work when appropriate.

### 22.3 Execute Approved State Change

1. Worker claims the isolated execution segment.
2. Revalidate lease, workflow state, authorization, approval, action hash, and cancellation.
3. In a short transaction, create or bind the durable tool execution and approval.
4. Invoke the adapter outside the transaction using stable idempotency identity.
5. Record definitive success or failure in a new transaction.
6. If outcome is unknown, bind approval and execution in reconciliation state and do not retry automatically.
7. Persist workflow continuation and progress.

### 22.4 Process Source

1. Validate current access, format, size, signature, version, path, and checksum.
2. Acquire content safely.
3. Extract and normalize into structured blocks.
4. Segment with stable provenance.
5. Index metadata, lexical content, and semantic vectors as applicable.
6. Mark version current only after required processing succeeds.
7. Record warnings, partial coverage, failure, staleness, or revocation accurately.

### 22.5 Generate Briefing

1. Retrieve authorized evidence using lexical and semantic search.
2. Fuse with RRF and optionally rerank.
3. Apply relevance rules and detect insufficiency.
4. Assemble stage-specific context.
5. Invoke normalized model capability.
6. Validate structured output.
7. Validate citation support separately from retrieval rank.
8. Persist draft, evidence relationships, limitations, and progress.
9. Present draft for revision and later artifact approval.

## 23. Implementation Guardrails

- No cross-module table modification.
- No repository-owned commits.
- No long transaction around provider, tool, storage, or human waits.
- No browser authority over approval or execution state.
- No automatic replay of uncertain state changes.
- No LangGraph checkpoint as the only record of business state.
- No provider or MCP SDK objects in workflow contracts.
- No raw source instructions promoted into platform policy.
- No universal memory dump into model context.
- No requirement that every source be embedded.
- No one-job-per-node coupling.
- No arbitrary secret inheritance by tools.
- No silent overwrite, provider fallback, budget increase, or authentication fallback.

## 24. Deferred Decisions

The following remain for the Data Design Document, API Contract, ADRs, or implementation design:

- Exact entity and table schemas
- Status enum storage and transition constraints
- Repository and Unit of Work library choices
- Job polling, lease, heartbeat, and retry values
- Outbox schema, dispatcher batch size, and retention
- LangGraph checkpoint adapter and physical tables
- Detailed workflow graph and node definitions
- Approval expiry defaults and action-hash canonicalization
- Tool schema serialization and MCP transport
- Parser libraries and normalized block schema
- Segmentation sizes and overlap
- RRF constants, candidate counts, thresholds, and reranker
- Embedding model, dimensions, and index type
- Context token allocations and summary triggers
- Provider selection and model identifiers
- SSE payload schema, batching interval, and retention
- OIDC provider, session lifetime, and CSRF implementation library
- Detailed artifact finalization sequence
- Telemetry backend, sampling, dashboards, and alerts
- CI/CD test gates

## 25. Consistency Review

The technical design is consistent with the PRD and HLA:

- Research-to-Briefing is implemented as one workflow, not embedded into generic platform infrastructure.
- Future non-research workflows reuse workflow, job, approval, tool, context, progress, security, and failure infrastructure.
- PostgreSQL remains authoritative while LangGraph retains only runtime-specific checkpoints.
- Human approval is durable, identity-bound, immutable, and replay-resistant.
- External work uses short transaction boundaries and honest at-least-once semantics.
- HTMX and SSE remain lean while supporting durable workflows.
- Hybrid retrieval preserves authorization and provenance.
- Provider, storage, identity, and MCP details remain behind ports.
- Observability and testing cover recovery and AI-quality risks without requiring excessive infrastructure.
- No accepted requirement conflict was identified.

## 26. Definition of Completion

This TDD is complete when it provides enough implementation behaviour to design authoritative data entities, relationships, constraints, retention, indexing, and lifecycle rules in the Data Design Document without prematurely finalizing public API payloads.
