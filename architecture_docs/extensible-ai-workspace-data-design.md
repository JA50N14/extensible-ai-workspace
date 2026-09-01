# Data Design Document: Extensible AI Workspace

## 1. Document Control

| Field | Value |
|---|---|
| Document | Data Design Document |
| Product | Extensible AI Workspace |
| Version | 1.0 |
| Status | Approved baseline for API contract and implementation |
| Owner | Jason Macfarlane |
| Inputs | Product Requirements Document v1.0; High-Level Architecture v1.0; Technical Design Document v1.0 |

## 2. Purpose and Scope

This document defines the durable data model for the Extensible AI Workspace. It establishes data ownership, bounded PostgreSQL schemas, entity relationships, authoritative versus derived data, relational and JSONB storage rules, identity, workflow execution, approvals, tools, content, retrieval, evidence, artifacts, events, retention, indexing, and migration strategy.

It intentionally does not define final HTTP payloads, HTMX fragments, SSE wire formats, ORM classes, SQL migration scripts, exact pgvector index parameters, or endpoint names. Those belong in the API Contract, ADRs, or implementation.

## 3. Data Design Principles

1. PostgreSQL is the authoritative store for durable platform and business state.
2. LangGraph or another workflow runtime owns only runtime-specific checkpoint data.
3. Durable externally referenced entities use UUIDv7 identifiers.
4. Relational columns represent stable, queryable, constrained, authorized, and lifecycle-significant data.
5. JSONB is bounded, typed, versioned, validated, and owned by one module.
6. Source and artifact history is immutable and versioned.
7. Generated content is not automatically equivalent to independent source evidence.
8. Cross-schema foreign keys protect integrity, while application modules retain mutation ownership.
9. Deletion is staged and reference-aware rather than an uncontrolled database cascade.
10. Indexes follow documented access patterns and measured query plans.
11. Schema evolution uses expand, migrate, and contract.
12. Historical records preserve what happened without allowing superseded information to act as current truth.

## 4. PostgreSQL Schema Organization

The modular monolith uses a small number of bounded PostgreSQL schemas.

### 4.1 `iam`

Owns:

- Internal users
- External identity mappings
- Server-side sessions
- Authentication-related security records

### 4.2 `workspace`

Owns:

- Workspaces
- Conversations
- Messages and message parts
- Conversation summaries
- Workspace decisions
- User and workspace preferences

### 4.3 `execution`

Owns:

- Workflow runs
- Durable execution segments
- Jobs and job attempts
- Runtime-checkpoint references
- Approval requests
- Tool definitions and executions
- Provider configurations and invocations
- Invocation-context references and usage
- Outbox events
- Handler deliveries
- Workflow progress events

### 4.4 `knowledge`

Owns:

- Logical sources
- Source versions
- Processing runs
- Normalized blocks
- Segment generations
- Retrieval segments
- Embedding-model definitions
- Embedding generations
- Segment embeddings
- Retrieval profiles
- Findings
- Evidence links
- Citation-validation state

### 4.5 `content`

Owns:

- Stored objects
- Logical artifacts
- Artifact versions
- Artifact relationships
- Artifact placements
- External exports
- Temporary-object and cleanup state
- Optional protected diagnostic captures

Database schemas organize related data but do not replace application module ownership.

## 5. Identifier and Time Strategy

Durable domain and execution entities use UUIDv7 primary identifiers. UUIDv7 permits application-side generation, cross-deployment uniqueness, and better insertion locality than random UUIDv4.

Explicit timestamp columns remain authoritative. Identifier ordering must not replace `created_at`, `occurred_at`, `effective_at`, or similar business timestamps.

Ordered children use explicit sequence values scoped to their parent, including:

- Message sequence within a conversation
- Progress-event sequence within a workflow run
- Segment sequence within a workflow run
- Block and retrieval-segment order within a source version or generation
- Artifact-version number within a logical artifact
- Job-attempt number within a job

All timestamps are stored in UTC with timezone-aware PostgreSQL types. Presentation converts them to user locale.

## 6. Relational and JSONB Storage Rules

### 6.1 Relational Core

A field is relational when it participates in:

- Identity
- Authorization
- Lifecycle transitions
- Foreign keys
- Uniqueness
- Job claiming or recovery
- Approval or reconciliation
- Retention or deletion
- Common filtering, sorting, reporting, or operational metrics

### 6.2 Bounded Versioned JSONB

JSONB is permitted when the payload:

- Varies by workflow, tool, event, or provider
- Is owned by one module
- Has a declared type and schema version
- Is validated by the application
- Has a size limit
- Does not hold primary cross-module relationships
- Is not required for frequent operational filtering

Examples include:

- Approval action snapshots
- Validated tool inputs
- Small normalized tool results
- Outbox and progress payloads
- Workflow-specific configuration
- Extraction warnings
- Non-secret provider settings and usage details
- Preference values

Every important JSONB payload has a type, schema version, owner, sensitivity classification, compatibility policy, and size limit.

### 6.3 Promotion Rule

A JSONB property is promoted to a typed relational column when it becomes significant for authorization, lifecycle, uniqueness, referential integrity, retention, frequent filtering, or operational reporting.

### 6.4 Large Content

Complete documents, large extracted text, full model prompts or responses, large tool results, binary artifacts, and conversation histories do not belong in routine JSONB. They use normalized records, pgvector columns, or the content-storage abstraction.

## 7. Cross-Schema Integrity and Ownership

Cross-schema foreign keys are used where a record must not exist without another durable entity.

Examples:

- `workspace.workspaces.owner_user_id -> iam.users.id`
- `execution.workflow_runs.workspace_id -> workspace.workspaces.id`
- `execution.approvals.workflow_run_id -> execution.workflow_runs.id`
- `knowledge.sources.workspace_id -> workspace.workspaces.id`
- `knowledge.source_versions.source_id -> knowledge.sources.id`
- `content.artifacts.workspace_id -> workspace.workspaces.id`
- `content.artifact_versions.stored_object_id -> content.stored_objects.id`

A foreign key does not grant mutation ownership. Modules modify their own data through owned repositories and application contracts. Cross-module read queries return purpose-built read models rather than mutable foreign ORM entities.

Mandatory circular foreign keys are avoided. Nullable convenience references such as current source version or current artifact version are maintained atomically by the owning module.

The application uses one normal runtime database role and a separate migration role. More granular database roles may be introduced later if practical need justifies them.

## 8. Identity and Session Model

### 8.1 Internal User

The internal user is the stable platform identity referenced by workspaces, workflows, approvals, preferences, artifacts, and authorization rules.

Core fields:

- User ID
- Status
- Display name
- Primary email where available
- Created and updated timestamps
- Disabled timestamp
- Deletion-requested timestamp
- Optimistic concurrency version

Statuses include `ACTIVE`, `DISABLED`, `DELETION_REQUESTED`, and `PURGED`.

### 8.2 External Identity Mapping

Maps an authentication source to an internal user.

Core fields:

- External-identity ID
- User ID
- Provider type
- Issuer
- Subject
- Created timestamp
- Last-authenticated timestamp
- Disabled timestamp
- Claims-profile version
- Bounded provider display metadata

A uniqueness constraint applies to `(issuer, subject)`.

Raw ID tokens, access tokens, refresh tokens, complete unfiltered claims, and authentication secrets are not stored in this entity.

### 8.3 Local Trusted Identity

Local mode uses a synthetic external-identity mapping:

- Provider type: `LOCAL_TRUSTED`
- Issuer: deployment-scoped local issuer
- Subject: configured local-user identity

The mapping does not itself enable local authentication. The deployment must be explicitly configured for safe local-trusted mode.

### 8.4 Server-Side Session

The browser receives an opaque cookie. PostgreSQL stores a secure hash or verifier rather than the raw token.

Core fields:

- Session ID
- User ID
- External-identity ID where applicable
- Authentication method
- Session-token hash
- Created and last-activity timestamps
- Idle and absolute expiry timestamps
- Revoked timestamp and reason
- Authentication timestamp
- Rotation generation
- CSRF verifier or protected reference
- Security-context version

Active state is determined from revocation and expiry. Security-sensitive transitions rotate the session token or generation.

Disabling a user prevents new sessions, revokes active sessions, and prevents new user-authorized operations while preserving historical ownership until purge.

## 9. Workspace and Conversation Model

### 9.1 Workspace

Core fields:

- Workspace ID
- Owner user ID
- Name
- Description
- Status
- Created, updated, archived, and deletion-requested timestamps
- Optimistic concurrency version

The workspace is the principal ownership and authorization boundary for conversations, workflows, sources, findings, artifacts, and preferences.

### 9.2 Conversation

A workspace may contain one or more conversations.

Core fields:

- Conversation ID
- Workspace ID
- Title
- Status
- Created and last-message timestamps
- Archived timestamp
- Optimistic concurrency version

### 9.3 Message

Messages are independently addressable and ordered.

Core fields:

- Message ID
- Conversation ID
- Optional workflow-run ID
- Sequence number
- Role or message type
- Status
- Created and completed timestamps
- Optional parent and superseded-message IDs
- Optional content-storage reference
- Length or token metadata
- Provenance classification
- Correlation ID

A unique constraint applies to `(conversation_id, sequence_number)`.

Supported message types may include user, assistant, workflow status, tool-result presentation, approval presentation, generated notice, error, and limitation.

### 9.4 Message Parts

Typed parts may represent text, source references, artifacts, tool results, approvals, structured results, warnings, and limitations. Small parts use versioned JSONB; large content uses storage references.

### 9.5 Conversation Summary

Summaries are derived and never replace source messages.

Core fields:

- Summary ID
- Conversation ID
- Summary version
- Included message range or set
- Summary-policy version
- Status
- Created timestamp
- Superseded-by summary ID
- Summary content or storage reference
- Source-message-set checksum

A summary becomes stale when its source set changes or its policy is no longer applicable.

## 10. Workspace Decisions and Preferences

### 10.1 Workspace Decision

Decisions are append-only historical records.

Core fields:

- Decision ID
- Workspace ID
- Decision key
- Decision type
- Status
- Title
- Decision text or structured value
- Rationale
- Recorded-by user ID
- Optional source message or workflow-run ID
- Created and effective timestamps
- Superseded timestamp
- Superseded-by decision ID
- Change reason
- Schema version

Statuses include `DRAFT`, `ACTIVE`, `SUPERSEDED`, and `WITHDRAWN`.

Only one active decision is permitted for a workspace and decision key, enforced by a partial unique constraint.

When a user changes a decision, one transaction creates the replacement as active, supersedes the old record, links both versions, records the reason and actor, and emits a durable event. Context Assembly uses active decisions by default. Derived outputs that depended on a superseded decision may be marked stale for review.

### 10.2 User Preference

Core fields:

- Preference ID
- User ID
- Namespace
- Preference key
- Value-schema version
- Bounded JSONB value
- Created, updated, and deleted timestamps
- Optional consent or source reference

A partial unique constraint permits one active preference per `(user_id, namespace, preference_key)`.

### 10.3 Workspace Preference

Workspace-scoped settings use a separate record or explicit workspace scope to prevent one workspace's assumptions from leaking into another.

Preferences are explicit. The platform does not infer and persist global user memory without user action.

## 11. Workflow Execution Model

### 11.1 Workflow Run

Represents one complete user or system workflow instance.

Core fields:

- Workflow-run ID
- Workspace ID
- Initiating user ID
- Workflow type and version
- Lifecycle status
- Current user-visible stage
- Progress summary
- Cancellation state
- Completion outcome
- Failure code
- Created, started, paused, and completed timestamps
- Retrieval-profile version where relevant
- Optimistic concurrency version

### 11.2 Durable Execution Segment

Represents one meaningful recoverable execution boundary.

Core fields:

- Segment ID
- Workflow-run ID
- Stable segment key and version
- Sequence
- Status
- Budget configuration or reference
- Start and completion timestamps
- Failure code
- Continuation relationship
- Checkpoint references before and after execution

### 11.3 Job

Represents executable work.

Core fields:

- Job ID
- Segment ID
- Job type
- Priority
- Status
- Eligible-at timestamp
- Current lease ID
- Current worker ID
- Lease expiry
- Attempt count
- Cancellation state
- Idempotency identity
- Created and completed timestamps

Eligible-job and expired-lease indexes support `FOR UPDATE SKIP LOCKED` claiming and recovery.

### 11.4 Job Attempt

Preserves each worker attempt.

Core fields:

- Attempt ID
- Job ID
- Attempt number
- Worker ID
- Lease ID
- Claimed, started, heartbeat, and ended timestamps
- Outcome
- Failure code
- Recovery reason
- Diagnostic correlation ID

A unique constraint applies to `(job_id, attempt_number)`.

### 11.5 Runtime Checkpoint Reference

The platform references, but does not duplicate, runtime-owned checkpoint payloads.

Core fields:

- Checkpoint-reference ID
- Workflow-run ID
- Optional segment ID
- Runtime type and version
- Thread or namespace identity
- Checkpoint identity
- Checkpoint-schema version
- Created timestamp
- Compatibility status
- Current indicator

Missing or incompatible checkpoints place the workflow in recovery rather than causing automatic restart.

## 12. Status Storage and State Enforcement

Statuses use text columns with PostgreSQL `CHECK` constraints. Domain state machines enforce valid transitions.

The database also enforces practical status-dependent consistency where possible, including:

- Completed records require completion timestamps.
- Pending approvals lack decision timestamps.
- Running jobs require active lease information.
- Available artifact versions reference available stored objects.
- Purged records have purge timestamps.

Platform lifecycle status remains separate from workflow-specific stage keys.

Optimistic concurrency and expected-prior-state predicates prevent silent overwrites during concurrent transitions.

## 13. Approval and Tool Model

### 13.1 Approval Request

Core fields:

- Approval ID
- Workspace ID
- Workflow-run ID
- Approval type
- Authorization semantics
- Status
- Requested-by and decided-by user IDs
- Created, expiry, decision, and consumed timestamps
- Proposal hash
- Canonicalization version
- Action-snapshot schema version
- Superseded-by approval ID
- Optional bound tool-execution ID
- Optimistic concurrency version
- Bounded versioned action snapshot JSONB

Approval statuses include `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `SUPERSEDED`, `CANCELLED`, and `CONSUMED`.

Single-action and defined-workflow-scope semantics are supported.

### 13.2 Tool Definition

Core fields:

- Stable tool ID and version
- Display name
- Origin type, including native or MCP
- Effect classification
- Approval policy
- Input- and output-schema versions
- Availability status
- Registration timestamp
- Bounded versioned schemas

### 13.3 Tool Execution

Core fields:

- Execution ID
- Workspace ID
- Workflow-run ID
- Segment ID
- Tool ID and version
- Effect classification
- Status
- Optional approval ID
- Idempotency key
- Invocation identity
- Input- and output-schema versions
- Started and completed timestamps
- External result ID
- Failure code
- Reconciliation status
- Correlation ID
- Optimistic concurrency version
- Bounded validated input and normalized result, or content-storage references

Execution statuses include proposed, waiting for approval, ready, running, succeeded, failed, cancelled, timed out, outcome uncertain, reconciling, and reconciled terminal outcomes.

### 13.4 Binding Constraints

- A single-action approval binds to at most one execution.
- A state-changing execution requiring approval must reference an eligible approval.
- Approval and execution belong to the same workspace and workflow run.
- Proposal hash, canonicalization version, tool identity, and validated arguments must match.
- Rejected, expired, superseded, cancelled, or consumed approvals cannot authorize new execution.
- Idempotency identity is unique within its defined scope.
- Uncertain execution cannot be recreated automatically under a new identity.

Application-domain checks complement database constraints where canonical JSON comparison or authorization semantics cannot be expressed through simple foreign keys.

## 14. Provider Configuration and Invocation

### 14.1 Provider Configuration

Versioned, non-secret configuration includes:

- Provider-configuration ID
- Capability type
- Adapter type
- Provider name and model identifier
- Configuration version
- Status
- Created, activated, and superseded timestamps
- Bounded non-secret settings JSONB
- Optional secret-reference name

Secret values are never stored.

### 14.2 Provider Invocation

Core fields:

- Invocation ID
- Workspace ID
- Workflow-run ID
- Segment ID
- Provider-configuration ID
- Capability and operation types
- Status
- Attempt number
- Started and completed timestamps
- Provider request ID where available
- Finish reason
- Failure code
- Correlation ID
- Parent invocation ID for retries or repair attempts
- Context-policy version
- Output-schema version

Statuses include prepared, running, succeeded, failed, timed out, rate limited, refused, cancelled, and invalid result.

### 14.3 Invocation Context Inputs

A join entity records the authoritative data used to assemble context:

- Invocation ID
- Context category
- Included entity type and ID
- Inclusion order
- Token count where available
- Truncation or exclusion metadata
- Context-policy version

Examples include messages, summaries, decisions, preferences, source segments, tool results, and structured workflow facts.

### 14.4 Usage

Normalized usage records retain input and output tokens, cached tokens where reported, embedded item counts, search usage, provider-reported cost, currency, measurement source, and schema version. Values are not fabricated when the provider does not report them.

### 14.5 Result References

Invocations reference platform-owned messages, findings, artifacts, embedding generations, result sets, or stored objects rather than duplicating complete outputs.

### 14.6 Protected Diagnostic Capture

Raw prompt or response capture is disabled by default. Explicit local diagnostic mode may create short-lived, restricted, clearly labelled captures under a separate retention class. Normal execution and evaluation cannot depend on them.

## 15. Source and Content-Processing Model

### 15.1 Logical Source

Represents the user-recognizable source.

Core fields:

- Source ID
- Workspace ID
- Source type and provenance class
- Display name
- Access status
- Current-version ID
- External location or stored-object reference
- Added, removed, and revoked timestamps
- Optimistic concurrency version

### 15.2 Immutable Source Version

Represents exact observed content.

Core fields:

- Source-version ID
- Source ID
- Content checksum
- Length and media type
- Observed or acquired timestamp
- Processing status
- Stored-object reference
- Superseded relationship
- Current-usable indicator

A new version becomes current only after minimum required processing succeeds. Historical citations retain the original version.

### 15.3 Processing Run

Captures one extraction and normalization attempt:

- Processing-run ID
- Source-version ID
- Parser and normalization policy versions
- Status
- Start and completion timestamps
- Failure code
- Warning summary
- Produced block-generation reference
- Activation status

Content change creates a new source version. Parser or policy change creates a new processing generation against the same source version.

### 15.4 Normalized Block

Core fields:

- Block ID
- Source-version ID
- Processing-run or block-generation ID
- Block sequence
- Block type
- Heading path
- Page and line locations where applicable
- Language or code metadata
- Text or content-storage reference
- Location metadata
- Content checksum

### 15.5 Source Revocation

Revocation prevents new reads and retrieval. It does not rewrite historical briefings or erase their provenance. Content purge follows retention policy separately.

### 15.6 Duplicate Content

Exact duplicate content may reuse processing or storage work, but logical source identity, workspace scope, access status, and citation provenance remain separate.

## 16. Segment and Retrieval Generations

### 16.1 Segment Generation

Represents one segmentation policy applied to one source version.

Core fields:

- Segment-generation ID
- Source-version ID
- Segmentation-policy name and version
- Normalization or block-generation reference
- Lexical-configuration version
- Status
- Segment count
- Created, completed, activated, and superseded timestamps
- Superseded-by generation ID
- Failure code

### 16.2 Retrieval Segment

Core fields:

- Segment ID
- Segment-generation ID
- Source-version ID
- Segment sequence
- Referenced block range or mapping
- Retrieval text or storage reference
- Citation location
- Lexical-search representation
- Content checksum
- Processing warnings

### 16.3 Embedding Model

Core fields:

- Embedding-model ID
- Adapter type and provider model identifier
- Configuration version
- Vector dimensions
- Distance metric
- Normalization behaviour
- Created timestamp
- Availability status

### 16.4 Embedding Generation

Core fields:

- Embedding-generation ID
- Segment-generation ID
- Embedding-model ID
- Status
- Expected and completed segment counts
- Started, completed, activated, and superseded timestamps
- Superseded-by generation ID
- Failure code

### 16.5 Segment Embedding

Core fields:

- Segment ID
- Embedding-generation ID
- Vector
- Content checksum
- Embedded timestamp
- Bounded provider usage metadata

A unique constraint prevents duplicate vectors for the same segment and generation.

### 16.6 Atomic Activation

A generation becomes searchable only after expected counts, dimensions, and validation succeed. Activation and supersession occur atomically. Failed or partial generations remain outside normal retrieval, preserving the previous active generation.

### 16.7 Retrieval Profile

A versioned retrieval profile identifies the active combination of segment policy, lexical configuration, embedding model/generation, RRF policy, limits, optional reranker, and relevance policy. Workflow runs record the profile version used.

The MVP uses one active segmentation policy, embedding model, and retrieval profile while preserving the ability to replace them safely.

## 17. Findings, Evidence, and Citations

### 17.1 Finding

Represents a meaningful claim, synthesis, recommendation, assumption, conflict, unknown, or limitation.

Core fields:

- Finding ID
- Workspace ID
- Workflow-run ID
- Finding type
- Status
- Canonical finding text
- Optional structured subject
- Created and validated timestamps
- Superseded timestamp and successor ID
- Finding-schema version
- Optimistic concurrency version

Finding types include `SUPPORTED_FACT`, `MULTI_SOURCE_SYNTHESIS`, `RECOMMENDATION`, `ASSUMPTION`, `CONFLICT`, `UNKNOWN`, and `LIMITATION`.

### 17.2 Evidence Link

Represents the relationship between one finding and one source passage.

Core fields:

- Evidence-link ID
- Finding ID
- Source ID
- Source-version ID
- Segment ID
- Relationship type
- Validation status
- Validation-method version
- Created and validated timestamps
- Validation failure code
- Relevant location metadata
- Schema version

Relationship types include supports, contradicts, qualifies, provides context, and identifies gap.

Validation states include proposed, validated, rejected, requires review, and unavailable.

### 17.3 Artifact Placement

Maps a finding into one artifact version:

- Placement ID
- Finding ID
- Artifact-version ID
- Section key
- Display order
- Rendered citation label
- Included text checksum
- Created timestamp

Citation numbering is artifact rendering metadata rather than durable citation identity.

### 17.4 Revision and Staleness

Materially edited findings are superseded and revalidated. Source-version changes do not rewrite historical findings. New research may flag dependent findings or artifacts for reassessment.

Not every prose sentence becomes a finding. The granularity is reserved for content requiring traceability, validation, conflict representation, reuse, or later reassessment.

## 18. Stored Objects and Artifacts

### 18.1 Stored Object

Represents physical content behind an opaque storage key.

Core fields:

- Stored-object ID
- Storage backend type
- Opaque storage key
- Object status
- Media type
- Byte size
- Content checksum
- Created, verified, and deleted timestamps
- Optional encryption metadata reference
- Retention status
- Storage-schema version

Statuses include pending, available, quarantined, missing, deletion pending, deleted, and failed.

### 18.2 Logical Artifact

Core fields:

- Artifact ID
- Workspace ID
- Artifact type
- Display name
- Status
- Created-by user ID
- Originating workflow-run ID
- Current-version ID
- Created, archived, and deleted timestamps
- Optimistic concurrency version

### 18.3 Artifact Version

Core fields:

- Artifact-version ID
- Artifact ID
- Version number
- Stored-object ID
- Media type and checksum
- Status
- Created-by user ID
- Workflow-run ID
- Created and finalized timestamps
- Supersedes-version ID
- Generation-policy version
- Optional approval ID
- Bounded output-specific metadata

Versions are immutable after finalization. Existing content is not overwritten silently.

### 18.4 Artifact Relationships

A relationship entity links parent and child artifacts using types such as contains, manifest for, metadata for, derived from, supersedes, and export of. It also records display order and required/optional status.

### 18.5 External Export

Represents approved delivery of an artifact version outside application-managed storage.

Core fields:

- Export ID
- Artifact-version ID
- Workflow-run ID
- Approval ID
- Destination type and reference
- Proposed and actual filename
- Overwrite policy
- Status
- Idempotency key
- Started and completed timestamps
- External result reference
- Failure or reconciliation state

Artifact content, managed storage location, and external delivery are distinct concepts.

### 18.6 Finalization

Bytes are written and verified under a stable object identity before one short transaction marks the object available, creates or finalizes the artifact version, updates the current version, and writes events. Failed commits leave orphan candidates that are not exposed as valid artifacts.

## 19. Outbox, Deliveries, and Progress

### 19.1 Outbox Event

Core fields:

- Outbox-event ID
- Event type and version
- Owning module
- Entity type and ID
- Optional workspace and workflow-run IDs
- Occurred and available-after timestamps
- Correlation and causation IDs
- Retention timestamp
- Payload schema version
- Bounded payload JSONB

### 19.2 Handler Delivery

Dispatcher-created delivery records track one handler's processing of one event.

Core fields:

- Delivery ID
- Outbox-event ID
- Stable handler key and version
- Status
- Attempt count
- Next-attempt timestamp
- Worker, lease ID, and lease expiry
- Attempt and completion timestamps
- Failure code
- Correlation ID

A unique constraint applies to `(outbox_event_id, handler_key)`. Delivery is at least once and handlers are idempotent.

Delivery statuses include pending, available, running, retry scheduled, completed, permanently failed, and cancelled.

### 19.3 Progress Event

Core fields:

- Progress-event ID
- Workflow-run ID
- Sequence number
- Event type and version
- User-visible stage
- Occurred timestamp
- Optional segment, job, approval, tool-execution, and artifact IDs
- Correlation ID
- Retention timestamp
- Bounded presentation payload JSONB

A unique constraint applies to `(workflow_run_id, sequence_number)`.

Outbox events drive application reactions. Progress events provide durable user-visible history and SSE reconnection. They remain separate.

### 19.4 Retention

Outbox events are purgeable only after all required deliveries reach terminal states and retention expires. Failed deliveries remain longer for diagnosis. Progress retention follows workflow-history policy and may be compacted because current workflow state remains authoritative.

## 20. Retention and Deletion

Deletion is staged:

```text
ACTIVE
  -> DELETION_REQUESTED
  -> RETAINED
  -> PURGE_ELIGIBLE
  -> PURGED
```

### 20.1 Deletion Request

A transaction marks the target unavailable, prevents new work, cancels eligible queued jobs, records actor and time, and emits cleanup events.

### 20.2 Retention Classes

- User content
- Operational execution data
- Security and authorization data
- Derived retrieval and summary data
- Infrastructure records
- Protected diagnostic captures

Each class receives configurable retention appropriate to its purpose.

### 20.3 Purge

An idempotent cleanup worker removes dependencies in safe order, including checkpoints, derived retrieval data, summaries, normalized content, unreferenced stored objects, conversations, workflow records, and finally parent records.

Full workspace deletion does not rely on a large database cascade.

### 20.4 Source Removal

Removing a source prevents new retrieval but preserves historical provenance. Content purge follows retention separately. Historical citations may retain non-content metadata after the passage is gone and must show that the original content is unavailable.

### 20.5 Shared Objects

A physical object is deleted only after all retained references are removed.

### 20.6 Backups

Purged data may remain in backups until backup expiry. Restored backups require deletion or purge replay so removed content is not restored permanently without review.

## 21. Foreign-Key Deletion Behaviour

Use `RESTRICT` or `NO ACTION` for authoritative historical relationships and carefully selected `CASCADE` only for tightly owned children with no independent lifecycle.

Suitable cascade candidates include:

- Message parts owned only by a message
- Segment embeddings owned only by an embedding generation
- Handler deliveries owned only by an outbox event after retention checks

Do not rely on cascade for:

- User to workspace
- Workspace to workflow runs
- Workflow run to approvals or tools
- Source to source versions
- Artifact to artifact versions

These use staged deletion.

## 22. Indexing Strategy

Indexes follow known access patterns and are refined using representative data and `EXPLAIN` plans.

### 22.1 Identity and Session

- Unique `(issuer, subject)`
- Unique session-token hash
- Active session lookup
- Session expiry cleanup

### 22.2 Workspace and Conversation

- Workspaces by owner and status
- Conversations by workspace and activity
- Unique message sequence per conversation
- Messages by conversation and sequence
- One active decision per workspace and decision key
- One active preference per user, namespace, and key

### 22.3 Execution

- Runs by workspace and creation time
- Runs by lifecycle status
- Segments by run and sequence
- Eligible jobs by status, eligibility, and priority
- Expired running jobs by lease expiry
- Attempts by job and attempt number
- Current checkpoint references
- Pending approvals and approval expiry
- Tool executions by run and creation time
- Unique idempotency scopes
- Reconciliation-required executions

### 22.4 Knowledge

- Sources by workspace and access status
- Versions by source and observation time
- Blocks and segments by generation and order
- Lexical full-text index
- Vector index selected after measured corpus evaluation
- Active processing, segment, embedding, and retrieval generations
- Findings by workflow run and type
- Evidence links by finding and validation state

### 22.5 Events and Content

- Undelivered outbox events by availability
- Handler deliveries by status and retry time
- Progress events by workflow and sequence
- Artifacts by workspace and status
- Versions by artifact and version number
- Unique storage key
- Stored objects by checksum where deduplication applies
- Purge-eligible and missing objects
- Exports by artifact version and time

Partial indexes target operational subsets such as eligible jobs, pending approvals, undelivered events, active sessions, reconciliation-required executions, and purge-eligible records.

General JSONB GIN indexes are not created by default. Important JSON properties are promoted to relational columns when appropriate.

Vector exact or approximate indexing is selected from measured corpus size, quality, filtering, latency, build time, memory, and update cost.

## 23. Authoritative and Derived Data

### Authoritative

- Users and identity mappings
- Workspace ownership and explicit preferences
- Messages as originally recorded
- Active and historical workspace decisions
- Workflow lifecycle
- Jobs, attempts, approvals, and tool outcomes
- Source identity and immutable content versions
- Artifact identity and immutable versions
- Findings and their evidence relationships
- Provider invocation envelopes

### Derived and Rebuildable

- Conversation summaries
- Normalized blocks from immutable source content
- Retrieval segments
- Lexical search representations
- Embeddings
- Reranking results
- Progress snapshots
- Cached provider outputs

Derived data retains generation and policy versions and can be rebuilt without silently changing historical source identity.

### External and Not Fully Controlled

- Approved local files
- External webpages
- Model and search providers
- MCP systems
- External tool targets
- Export destinations

Platform records preserve observations, references, failures, and external result IDs without claiming control over the external system.

## 24. Schema Migration and Compatibility

Use append-only, ordered migrations with expand, migrate, and contract.

### 24.1 Expand

Add nullable columns, new tables, payload versions, statuses, and compatible indexes. Deploy readers capable of old and new representations.

### 24.2 Migrate

Backfill in bounded batches, transform payloads, verify counts and constraints, and move active writes to the new representation.

### 24.3 Contract

After old readers and writers are gone, remove compatibility paths, tighten constraints, remove obsolete structures, and drop superseded indexes.

### 24.4 Ownership

Each bounded schema owns its migrations, while one ordered history coordinates cross-schema dependencies. A designated deployment step applies migrations. Web and worker runtimes never race to migrate.

### 24.5 Runtime Compatibility

Each release declares supported schema ranges. Readiness fails outside that range. Incompatible web and worker releases do not process the same workflow state.

A maintenance window is acceptable for changes that cannot be made safely online.

### 24.6 Payload Compatibility

Evolving JSONB, outbox, progress, tool, preference, and provider payloads retain type, schema version, owner, validation model, and compatibility reader or migration path. Unknown versions fail safely.

### 24.7 Checkpoint Compatibility

Checkpoint references include workflow, runtime, and checkpoint versions. Compatible checkpoints resume; known versions may migrate; incompatible versions enter `RECOVERY_REQUIRED`; missing checkpoints never trigger blind restart.

### 24.8 Backfill Records

Long-running backfills record identifier, target version, status, cursor, timestamps, failure, and verification result so interrupted work resumes safely.

### 24.9 Rollback

Safe rollback prefers deploying earlier application code while expanded structures remain compatible. Destructive contract migrations require recovery notes. Rollback never assumes external actions can be reversed or newer checkpoints can be loaded by older code.

## 25. Integrity and Consistency Review

The data design is consistent with the PRD, HLA, and TDD:

- PostgreSQL remains authoritative for durable product and execution state.
- LangGraph remains isolated to runtime checkpoints.
- Research-to-Briefing uses generic workspace, workflow, tool, approval, source, evidence, artifact, and event infrastructure.
- Future non-research workflows can use shared entities and bounded JSONB without requiring schema changes for every extension.
- Genuinely new durable domain concepts may introduce dedicated relational structures.
- Source versions, findings, citations, decisions, and artifact versions preserve history without acting as current truth when superseded.
- State-changing actions remain approval-bound, idempotent, and reconcilable.
- User memory is explicit rather than inferred globally.
- Remote identity is decoupled from internal ownership.
- Storage, retrieval, events, and provider invocations remain independently versioned and observable.
- Staged deletion coordinates relational data, checkpoints, embeddings, and stored objects.
- No accepted requirement conflict was identified.

## 26. Principal Entity Relationships

```text
iam.user
  ├── iam.external_identity
  ├── iam.session
  ├── workspace.workspace
  └── workspace.user_preference

workspace.workspace
  ├── workspace.conversation
  │     ├── workspace.message
  │     └── workspace.conversation_summary
  ├── workspace.workspace_decision
  ├── workspace.workspace_preference
  ├── execution.workflow_run
  ├── knowledge.source
  ├── knowledge.finding
  └── content.artifact

execution.workflow_run
  ├── execution.segment
  │     ├── execution.job
  │     │     └── execution.job_attempt
  │     └── execution.checkpoint_reference
  ├── execution.approval
  ├── execution.tool_execution
  ├── execution.provider_invocation
  ├── execution.progress_event
  └── content.artifact

knowledge.source
  └── knowledge.source_version
          ├── knowledge.processing_run
          ├── knowledge.normalized_block
          └── knowledge.segment_generation
                  ├── knowledge.retrieval_segment
                  └── knowledge.embedding_generation
                          └── knowledge.segment_embedding

knowledge.finding
  ├── knowledge.evidence_link -> knowledge.retrieval_segment
  └── content.artifact_placement -> content.artifact_version

content.stored_object
  ├── knowledge.source_version
  ├── content.artifact_version
  └── optional large result or diagnostic references

content.artifact
  ├── content.artifact_version
  ├── content.artifact_relationship
  └── content.external_export

execution.outbox_event
  └── execution.handler_delivery
```

## 27. Deferred Physical Decisions

The following remain for implementation, API design, or ADRs:

- Exact table and column names
- ORM and migration libraries
- Exact check-constraint expressions
- UUIDv7 library
- Timestamp precision
- Session token and CSRF verifier algorithms
- Approval canonicalization and hashing algorithm
- Exact status values for every entity
- Parser-specific block payload schemas
- Segment sizes and overlap
- Retrieval-profile values and RRF constants
- Embedding model and dimensions
- pgvector physical layout and index type
- Content-store object-key format
- Deduplication scope
- Progress and outbox retention durations
- Deletion retention durations
- Provider usage normalization details
- Diagnostic-capture encryption and access
- Backfill batch sizes
- Migration tooling and release gates

## 28. Definition of Completion

This Data Design Document is complete when it provides enough durable entity, relationship, ownership, versioning, integrity, indexing, retention, and migration direction to define external and browser-facing contracts in the API Contract without embedding transport concerns into the database model.
