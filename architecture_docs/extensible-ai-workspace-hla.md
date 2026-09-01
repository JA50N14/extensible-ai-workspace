# High-Level Architecture: Extensible AI Workspace

## 1. Document Control

| Field | Value |
|---|---|
| Document | High-Level Architecture (HLA) |
| Product | Extensible AI Workspace |
| Version | 1.0 |
| Status | Approved baseline for technical design |
| Owner | Jason Macfarlane |
| Input | Product Requirements Document v1.0 |

## 2. Purpose

This document translates the approved product requirements into system boundaries, major logical components, runtime roles, trust boundaries, external dependencies, principal data flows, and deployment topology. It intentionally defers database schemas, endpoint contracts, class designs, prompt templates, graph nodes, retry values, and repository structure to later design documents.

## 3. Architecture Drivers

The architecture is primarily driven by:

1. A production-quality Research-to-Briefing Package as the first flagship workflow.
2. Support for future research and non-research tools and workflows without redesigning core platform infrastructure.
3. Durable workflows that can pause for approval, survive restarts, recover from failure, and expose progress.
4. Explicit user control over local content, broader web research, and state-changing actions.
5. Source provenance and hybrid retrieval across approved content.
6. Local development, practical self-hosting, and straightforward deployment to container-capable cloud infrastructure.
7. A lean server-rendered frontend that does not consume disproportionate project effort.
8. One user per initial deployment and bounded resource consumption.
9. A solo-developer scope that avoids premature microservices and unnecessary infrastructure.

## 4. Architectural Style

The system uses a **modular monolith with a separate worker runtime**.

- One cohesive codebase and application image contains the application modules.
- The web runtime handles browser interaction, authentication, authorization, validation, workflow submission, approvals, status delivery, and artifact views.
- The worker runtime handles durable, long-running, or resource-intensive workflow stages.
- Web and worker roles share application contracts and releases but run as separate processes or containers.
- PostgreSQL coordinates durable work and stores authoritative application state.
- The design is not a microservice architecture.
- Additional services will be extracted only when measured scaling, isolation, ownership, or deployment requirements justify them.

The preferred evolution path is to strengthen module boundaries first, scale worker capacity second, and introduce additional distributed infrastructure only in response to demonstrated need.

## 5. System Context

### 5.1 Primary Actor

The primary actor is a technically capable individual user. In local deployment the user may also be the deployment operator and extension developer.

The user creates workspaces, supplies objectives and sources, approves content access and research expansion, reviews outputs, approves state-changing actions, configures providers, and may add trusted tools or workflows.

### 5.2 System Boundary

The Extensible AI Workspace owns:

- Browser experience
- Authentication enforcement and application authorization
- Workspace and conversation state
- Workflow definitions, execution state, and lifecycle
- PostgreSQL-backed job coordination
- Source inventory, provenance, and access records
- Content-processing coordination
- Knowledge indexing and retrieval coordination
- Tool and workflow discovery and execution
- Approval policy and approval records
- Briefing and artifact generation
- Provider selection and invocation
- Operational logs, metrics, traces, and health information

### 5.3 External Systems

External boundaries include:

- Model inference provider
- Embedding provider if semantic indexing requires one
- Web-search provider
- External webpages
- Approved local folders
- Application-managed filesystem or object storage
- Future external tools and systems
- Configured MCP servers
- Remote OIDC identity provider
- Deployment-specific secret source
- Telemetry backend when configured

The application does not own the availability, accuracy, pricing, or internal behavior of external providers.

## 6. Runtime Topology

### 6.1 Web Runtime

The web runtime:

- Serves server-rendered HTML and HTMX fragments
- Exposes application endpoints
- Establishes identity and performs authorization
- Validates commands and user inputs
- Creates durable workflow runs and jobs
- Records approval decisions
- Streams progress through Server-Sent Events
- Provides polling fallback
- Displays workspaces, sources, tool activity, outputs, and artifacts

### 6.2 Worker Runtime

The worker runtime:

- Claims eligible PostgreSQL jobs using leases
- Executes controlled workflow stages
- Processes supported documents
- Invokes model, search, webpage, retrieval, and tool capabilities
- Persists checkpoints and progress
- Pauses workflows for input or approval
- Generates briefings and artifact packages
- Applies retry, idempotency, cancellation, and reconciliation policy

### 6.3 PostgreSQL

PostgreSQL is:

- The authoritative store for users, workspaces, runs, jobs, approvals, sources, provenance, artifacts, tool executions, settings, and operational state
- The MVP coordination mechanism between web and worker runtimes
- The initial platform for relational metadata, lexical search, and vector search if validated in technical design

The job queue and workflow state machine remain separate concepts. Queue state determines executable eligibility; workflow state represents business lifecycle, checkpoints, approvals, partial results, and recovery.

### 6.4 Content Storage

File content is stored behind a platform-owned storage contract:

- Local filesystem implementation for local development and simple self-hosting
- Object-storage implementation for remote or cloud deployment when introduced
- PostgreSQL retains authoritative metadata, ownership, checksums, provenance, versions, and storage references
- Approved local folders remain external source locations and are not copied automatically

## 7. User Interface Architecture

The browser client is a lean, server-rendered web application with HTMX-style progressive enhancement. React or another heavy single-page framework is not required.

The stable application shell provides:

- Workspace navigation
- Conversation and input
- Workflow selection and initiation
- Source and artifact views
- Workflow progress
- Tool activity
- Approval requests
- Notifications and errors
- Settings and provider status

Common workflow interactions use reusable server-rendered components. Specialized workflows may add localized views when generic chat, forms, status, approval, tool-result, and artifact components are insufficient.

A conforming workflow can participate in the standard lifecycle without changing the application shell. Zero frontend change is not guaranteed for workflows requiring specialized interaction. The MVP will not build a universal metadata-driven UI or no-code application builder.

The backend remains authoritative for workflow definitions, durable state, permissions, effect classification, approval validity, execution eligibility, tools, and artifact records.

## 8. Major Logical Modules

### 8.1 Identity and Access

Owns local trusted-user mode, remote OIDC integration, internal user identity, sessions, workspace ownership, authorization checks, and access enforcement.

### 8.2 Workspace

Owns workspace lifecycle, objectives, conversation associations, configuration, and relationships to sources, runs, outputs, and artifacts. This module is workflow-neutral.

### 8.3 Workflow

Owns workflow registration and discovery, initiation, durable lifecycle, stage state, progress, pause, resume, cancellation, retry eligibility, completion, and workflow-specific output references.

### 8.4 Job Coordination

Owns job submission, safe claiming, worker leases, ownership, retry availability, cancellation flags, and execution status. It does not define workflow business semantics.

### 8.5 Approval

Owns action snapshots, approval requests, approval, modification, rejection, expiration, consumption, and linkage between a decision and the exact proposed action.

### 8.6 Tool Registry and Execution

Owns normalized tool discovery, metadata, schema validation, effect classification, approval integration, invocation, result normalization, timeout and error handling, and outcome records.

### 8.7 Source

Owns source inventory, provenance, local-folder approvals, uploads, URLs, availability, processing state, source removal, and access revocation.

### 8.8 Content Processing

Owns format detection, extraction, normalization, segmentation, metadata preservation, and processing errors. It emits a normalized internal content representation.

### 8.9 Knowledge and Retrieval

Owns metadata filtering, lexical indexing and search, semantic indexing and search, scoped retrieval, evidence candidates, and provenance preservation. It returns evidence candidates rather than final answers.

### 8.10 Research

Owns Research-to-Briefing-specific planning, evidence-gap detection, web-research proposals, evidence collection, conflict identification, and briefing-synthesis coordination. Generic platform modules do not depend on Research.

### 8.11 Artifact

Owns draft outputs, briefing versions, manifests, metadata outputs, previews, filename conflicts, external file creation, and artifact records.

### 8.12 Provider Integration

Owns provider-neutral capabilities for model inference, embeddings if required, web search, webpage retrieval, normalized errors, and usage metadata.

### 8.13 Operational Support

Owns structured logging, metrics, traces, correlation identifiers, health, readiness, and failure categorization.

## 9. Dependency Direction

Workflow-specific modules depend on stable platform capabilities. Platform modules do not depend on Research-to-Briefing concepts.

A Research workflow may use Workflow, Source, Content Processing, Knowledge and Retrieval, Tools, Approval, Artifacts, Providers, and Operational Support. Workspace, Approval, Tool Execution, Job Coordination, and Artifact infrastructure remain workflow-neutral.

Modules communicate through defined application contracts rather than another module's internal persistence implementation. Direct database access across module ownership boundaries is prohibited by design.

## 10. Workflow Orchestration

The platform uses **controlled workflows with bounded agentic stages**.

Deterministic application logic controls:

- Lifecycle state
- Permissions
- Tool availability
- Approval checkpoints
- Retries
- Cancellation
- Completion conditions
- Durable persistence

Models may select among authorized capabilities or make bounded decisions only within stages that explicitly permit that discretion. Models may propose state-changing actions but cannot authorize them or alter platform policy.

All workflows map to a common lifecycle:

- Created
- Validating
- Ready
- Running
- Waiting for input or approval
- Completed
- Completed with limitations
- Cancelled
- Failed

Workflow definitions declare identity, version, required inputs, internal stages, allowed tools, agentic permissions, approval points, progress events, outputs, completion conditions, cancellation, retry behavior, errors, and optional specialized UI needs.

LangGraph is a candidate orchestration implementation behind an internal runtime boundary. Workspace identity, approvals, tools, artifacts, and durable business state do not become LangGraph-specific domain concepts.

## 11. Job Execution and Recovery

The system uses **at-least-once job processing with idempotency and reconciliation safeguards**.

Safeguards include:

- Stable execution identifiers
- Concurrency-safe job claiming
- Renewable worker leases
- Persisted stage completion
- Idempotency keys for state-changing tools where supported
- Pre-execution checks
- External result identifiers
- Failure-category-based retry policy
- Reconciliation for uncertain outcomes

The application does not claim exactly-once external execution. It avoids knowingly repeating completed work and does not automatically retry unsafe actions when the earlier effect cannot be established.

Normalized failure categories include validation, configuration, authorization, transient dependency, rate limit, permanent source, tool-declared business failure, uncertain execution outcome, and application defect.

Cancellation is cooperative. Queued jobs may be cancelled immediately; running stages observe durable cancellation at safe checkpoints. Completed external effects are not automatically reversed.

Approval authorizes an immutable proposed-action snapshot. Material changes to target, arguments, destination, affected files, or expected effect require new approval.

## 12. Knowledge and Retrieval

The system uses **hybrid retrieval** behind the Knowledge and Retrieval module:

- Metadata and authorization filtering
- Exact or lexical search
- Semantic vector search
- Workspace and source-scope filtering
- Later ranking or fusion as validated by evaluation

The initial implementation may use PostgreSQL relational metadata, full-text search, and pgvector if technical design confirms suitability. A dedicated external search platform is deferred.

Retrieval returns passages, locations, source identities, provenance, and retrieval signals. It does not create final answers or decide research conclusions.

Not every source must be embedded immediately. The architecture supports direct use of small sources, deferred indexing, re-indexing, exclusions, and source-specific strategies.

## 13. Tools and Extension Model

The platform owns a common internal tool contract with:

- Native trusted-tool adapters
- MCP adapters
- Future adapters if justified

A normalized tool declares stable identity, version, purpose, input and output schemas, read-only or state-changing effects, approval policy, configuration needs, timeout and cancellation capabilities, error categories, origin, and availability.

The platform owns authorization, validation, effect classification, approval enforcement, execution records, timeout policy, persistence, error normalization, status, and idempotency requirements.

Adapters own protocol discovery, schema translation, credential use, invocation, protocol errors, supported cancellation, and result translation.

MCP metadata is not trusted platform policy. MCP servers are operator-configured and trusted in the MVP. The platform may impose stricter effect classification and approval. Untrusted public MCP installation is outside scope.

## 14. External Provider Strategy

The MVP implements one working provider for each required external capability behind stable internal contracts. Workflow logic depends on provider-neutral contracts, not vendor SDK types.

Multiple providers in the MVP are not required. Additional providers may be added later through adapters and contract tests.

## 15. Identity and Authorization

The platform uses a deployment-specific identity adapter:

- **Local trusted-user mode** for loopback or explicitly trusted local development
- **Remote OIDC mode** for remotely reachable deployments

Remote deployments fail closed when OIDC is missing or invalid and must not silently fall back to trusted-local mode.

External identity is mapped to an internal user. Authorization is based on explicit ownership and permissions, even though the initial release supports one user per deployment.

The backend authorizes workspace access, source changes, workflow commands, approvals, tools, artifact access, downloads, writes, and provider configuration. HTMX requests receive the same authorization, validation, session, and CSRF protections as other browser requests.

## 16. Runtime Communication

User commands, forms, cancellation, and approval decisions use ordinary authenticated HTTP and HTMX requests.

Server-to-browser progress and text streaming use Server-Sent Events. Polling provides compatibility and reconnection fallback.

SSE is not an authoritative event store. Workflow state and progress are durable in PostgreSQL. A disconnected client reconstructs current state after reconnecting without restarting the workflow.

Common event categories include stage change, progress, output fragment, tool start and completion, approval required, pause, resume, completion, cancellation, and failure.

## 17. Context and Memory Boundaries

The platform separates:

1. Conversation context
2. Structured workflow state and checkpoints
3. Workspace knowledge and artifacts
4. Explicit user memory and preferences

Model context is assembled using the minimum relevant authorized information rather than replaying all retained data.

Generated content does not automatically become trusted external evidence. Origin, evidence links, approval, and content type remain distinguishable.

The MVP limits cross-workspace user memory to explicit settings and user-saved preferences. Automatic personal-fact extraction, behavioral profiling, and global semantic retrieval across all workspaces are deferred.

Shared persistence covers conversations, workflow runs, checkpoints, approvals, tool executions, sources, knowledge, artifacts, and explicit preferences. Versioned structured payloads may store bounded workflow-specific state. Dedicated relational persistence is introduced only for a durable first-class domain concept requiring constraints, querying, reporting, or an independent lifecycle.

## 18. Configuration and Secrets

The platform uses a configuration abstraction with deployment-specific secret sources.

- Local development may use environment variables and ignored local secret files.
- Self-hosting may use environment variables or mounted secret files.
- Cloud deployments may use managed secret stores through deployment adapters.
- Secrets remain outside source control and application images.
- Modules request named configuration through the application boundary rather than reading environment variables throughout the codebase.
- Web and worker roles receive only required credentials.
- Logs, traces, state, approvals, outputs, and artifacts redact secrets.
- Optional provider failure disables only the affected capability when safe.
- MCP adapters do not inherit unrelated credentials.

## 19. Observability

The system adopts an **OpenTelemetry-compatible** model incrementally.

Required telemetry includes:

- Structured logs for security outcomes, workflows, jobs, leases, approvals, tools, providers, sources, artifacts, and defects
- Metrics for HTTP behavior, queue depth and wait, workflow duration and results, worker duration, tool and provider outcomes, source failures, research limitations, and provider-supplied usage
- Traces across the primary browser-to-artifact workflow
- Health and readiness information

Telemetry correlates requests, users where safe, workspaces, runs, jobs, tools, providers, and approvals.

Raw prompts, complete model responses, document content, retrieved passages, tokens, API keys, and sensitive tool arguments are excluded by default. Local diagnostic capture may be explicitly enabled with clear warnings.

The application emits vendor-neutral telemetry and does not require a large observability stack for local startup.

## 20. Security and Trust Boundaries

### Browser to Backend

Browser input is untrusted. The backend validates identity, authorization, input schemas, approvals, artifact destinations, source permissions, and commands.

### Source Content to Application

Files, webpages, code, configuration, uploads, and model outputs are untrusted content rather than authorized instructions. They cannot alter policy, approve tools, expand access, or disclose credentials.

### Application to External Providers

The application controls what data leaves its boundary, which provider receives it, and which operation caused transmission. Local-folder permission does not imply permission to disclose content externally.

### Web Runtime to Worker

The worker validates job eligibility, permissions, approval, cancellation state, lease ownership, and prior completion before execution.

### Application to MCP and External Tools

External tool systems receive only scoped credentials and inputs. Their metadata and results do not override platform security policy.

## 21. Deployment Architecture

One application image runs in separate roles:

- Web container
- Worker container

Supporting infrastructure includes PostgreSQL and persistent application-managed file storage. A remote deployment may add ingress, TLS termination, managed PostgreSQL, object storage, managed secrets, and a telemetry backend.

A local composition includes web, worker, PostgreSQL, and local storage. Approved user folders are mounted separately and deliberately scoped.

A designated deployment step applies database migrations. Runtime instances do not race to migrate the schema. Web and worker versions must remain schema-compatible during upgrades.

The design is cloud-ready rather than cloud-agnostic at any cost. One reference cloud deployment may be selected later without implementing equivalent Azure and AWS deployments.

## 22. Scalability and Resource Controls

The MVP targets one user per deployment, one web runtime, one worker runtime, and bounded concurrency.

Deployment limits are configurable and workflows define stricter budgets where needed. Controls include upload size, extracted-content size, sources, concurrent jobs, worker concurrency, runtime, tool duration, retries, web breadth, model usage where measurable, research iterations, pages retrieved, evidence candidates, revision cycles, and agentic tool calls.

When a budget is exhausted, the platform stops additional consumption, preserves work, identifies the limit, produces a partial result where useful, and allows the user to narrow scope or authorize a larger configured limit.

Scaling proceeds by adjusting resources, increasing bounded worker concurrency, adding workers, scaling web instances, optimizing measured retrieval bottlenecks, and adding caching. Redis, a dedicated broker, or extracted services require measured justification.

## 23. Backup and Recovery

The architecture uses layered backup and recovery, with low implementation priority beyond essential recoverability.

### MVP Must

- Document backup and restore requirements for PostgreSQL and application-managed storage
- Preserve relationships between metadata and stored objects
- Detect missing stored objects after restoration
- Recover interrupted workflows from durable state
- Reconcile uncertain external actions rather than replay them

### Post-MVP / Low Priority

- Versioned user-facing workspace export and import

### Out of Scope

- Application-managed point-in-time recovery
- Cross-region replication
- Automated disaster recovery
- Enterprise retention
- Automatic cloud backup provisioning
- Restoration of external side effects

## 24. Principal End-to-End Flow

1. The browser submits an authenticated command to create or start a workflow.
2. The web runtime authorizes and validates the request.
3. The application persists workflow and job state in PostgreSQL.
4. The worker safely claims the job under a lease.
5. The workflow executes deterministic stages and bounded agentic stages.
6. Sources are processed and evidence is retrieved within authorized scope.
7. External providers and tools are invoked through internal contracts.
8. Progress is persisted and delivered through SSE.
9. The workflow pauses durably when user input or approval is required.
10. The authenticated user's decision is validated against the immutable action snapshot.
11. The worker resumes eligible work.
12. State-changing execution uses idempotency and reconciliation safeguards.
13. Outputs and artifacts are persisted and exposed through the workspace.
14. Logs, metrics, and traces correlate the complete operation.

## 25. Major Decisions

- Modular monolith plus separate worker
- PostgreSQL-backed durable job coordination
- Lean server-rendered HTMX frontend
- One application image with web and worker runtime roles
- Filesystem/object-storage abstraction
- Hybrid retrieval behind Knowledge and Retrieval
- Controlled workflows with bounded agentic stages
- One implemented provider per capability behind internal contracts
- Platform-owned tool model with native and MCP adapters
- At-least-once processing with idempotency and reconciliation
- Local trusted-user identity plus remote OIDC
- SSE plus HTTP commands and polling fallback
- Explicitly separated context and memory categories
- Deployment-specific configuration and secret sources
- OpenTelemetry-compatible observability
- Configurable deployment limits and workflow budgets
- Layered backup with workspace export deferred

## 26. Deferred Technical Decisions

- Exact PostgreSQL schemas and indexes
- Exact job-claim SQL, lease duration, heartbeat, and retry values
- LangGraph adoption and adapter details
- Content normalization and chunking rules
- Retrieval fusion and ranking algorithm
- Embedding model and dimensionality
- Exact model and web-search providers
- MCP transport, configuration, and trust details
- Storage contract and object naming
- Session implementation and OIDC provider
- CSRF and browser security implementation
- SSE event schema and persistence strategy
- Context assembly and summarization rules
- Default resource budgets
- Telemetry backend and sampling
- Deployment migration and rollback procedure
- Reference cloud deployment target
- Workspace export format

## 27. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Module boundaries erode inside the monolith | Explicit ownership, contracts, and dependency direction |
| PostgreSQL job coordination becomes complex | Keep concurrency bounded and define leases, checkpoints, and failure states in the TDD |
| Generic extension design becomes over-engineered | Build the flagship first and validate with one unrelated reference capability |
| HTMX UI becomes research-specific | Stable workflow shell plus localized specialized views |
| External providers leak into workflows | Provider-neutral contracts and normalized errors |
| MCP weakens security | Trusted configuration, scoped credentials, and platform-enforced policy |
| Retrieval returns plausible but weak evidence | Hybrid retrieval, provenance, citation evaluation, and separation from synthesis |
| Retry duplicates an external action | Stable identifiers, idempotency, result records, and reconciliation |
| Telemetry leaks sensitive content | Metadata-first telemetry and content exclusion by default |
| Remote deployment is exposed without authentication | Fail-closed OIDC mode |
| Resource use becomes unpredictable | Configurable limits and workflow budgets |
| Too much infrastructure delays completion | PostgreSQL coordination, one image, no required Redis or broker |

## 28. Consistency Review

The architecture is consistent with the PRD:

- Research-to-Briefing remains the flagship rather than the platform boundary.
- Generic workflow, tool, approval, artifact, context, and UI infrastructure supports later non-research capabilities.
- Local folder access is limited to deployments that can reach approved paths.
- Remote authentication is mandatory, while local development remains lightweight.
- State-changing actions require durable, identity-bound approval.
- Source traceability is supported by provenance-preserving processing and retrieval.
- Self-hosting remains practical with one image, two runtime roles, PostgreSQL, and storage.
- Cloud readiness does not create a requirement to support every cloud equally.
- The architecture adds production-aware recovery and observability without adopting premature microservices.

No unresolved contradiction requires reopening an accepted PRD decision.

## 29. Definition of Completion

This HLA is complete when it is sufficient to guide the Technical Design Document's detailed treatment of module contracts, runtime sequences, state machines, persistence behavior, failure handling, security mechanics, and implementation boundaries without prematurely defining data schemas or public API payloads.
