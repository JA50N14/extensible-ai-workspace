# API Contract: Extensible AI Workspace

## 1. Document Control

| Field | Value |
|---|---|
| Document | API Contract |
| Product | Extensible AI Workspace |
| Version | 1.0 |
| Status | Approved baseline for implementation |
| Owner | Jason Macfarlane |
| Inputs | PRD v1.0; HLA v1.0; TDD v1.0; Data Design Document v1.0 |

## 2. Purpose and Scope

This document defines the externally observable contracts used by the browser, HTMX interactions, JSON clients, SSE consumers, and future integrations. It specifies transport boundaries, endpoint conventions, authentication, CSRF, resources, commands, asynchronous operations, errors, pagination, concurrency, idempotency, discovery, uploads, workflows, approvals, conversations, findings, artifacts, health, rate limits, versioning, documentation, and contract testing.

It does not define SQL schemas, ORM models, LangGraph nodes, provider SDK types, internal Python ports, HTML styling, or every workflow-specific screen.

## 3. Contract Principles

1. HTML/HTMX, JSON, and SSE are separate presentation contracts over shared application use cases.
2. JSON resources expose stable platform concepts rather than database, worker, lease, checkpoint, or LangGraph internals.
3. Resource queries and ordinary editable attributes are resource-oriented.
4. Domain transitions and side effects use explicit commands.
5. Long-running work returns `202 Accepted` with a monitorable operation representation.
6. Server-owned lifecycle fields are output-only.
7. Mutations use optimistic concurrency where stale state matters and idempotency keys where duplicates create cost or side effects.
8. Errors use Problem Details with stable platform extensions.
9. Collection pagination is cursor-based by default.
10. Source, artifact, approval, finding, and workflow resources preserve the distinctions defined in the durable data model.
11. Session cookies authenticate all MVP browser, JSON, and SSE access. Machine authentication is deferred.
12. Untrusted content is always returned as data, never executable UI instructions.

## 4. Transport and Route Boundaries

### 4.1 Browser and HTMX

```text
/app/...
```

Returns complete server-rendered pages, trusted application fragments, redirects, and safe validation fragments.

### 4.2 Machine-Readable JSON

```text
/api/v1/...
```

Returns JSON resources, collections, operations, and Problem Details.

### 4.3 Server-Sent Events

```text
/events/...
```

Streams stable platform event families with versioned workflow-specific detail.

### 4.4 Authentication

```text
/auth/...
```

Handles login, callback, logout, and session inspection.

### 4.5 Health

```text
/health/live
/health/ready
```

Returns minimal deployment health. Detailed capability status is authenticated under `/api/v1/capabilities`.

Explicit route namespaces are preferred over complex content negotiation. HTML and JSON handlers call the same application use cases but use different presentation models.

## 5. Authentication, Sessions, and CSRF

### 5.1 MVP Authentication

All MVP HTML, JSON, and SSE contracts use an opaque server-side application session.

Remote deployments establish identity through OIDC and then create or rotate an application session. Local mode resolves the synthetic `LOCAL_TRUSTED` identity only when safe local mode is explicitly enabled.

Non-browser machine authentication, personal access tokens, OAuth service clients, and service identities are deferred.

### 5.2 Authentication Routes

```text
GET  /auth/login
GET  /auth/callback
POST /auth/logout
GET  /auth/session
```

`GET /auth/login` begins OIDC login or establishes the configured trusted local session. Return destinations must be validated application paths.

`GET /auth/callback` validates OIDC state, nonce, issuer, audience, and authorization response, maps the external identity, and establishes the application session.

`POST /auth/logout` requires CSRF protection, revokes the current application session, and clears the cookie.

`GET /auth/session` returns safe user and session metadata but never returns session tokens, provider tokens, complete claims, or CSRF verifiers.

### 5.3 Cookie Requirements

Remote session cookies use:

- `Secure`
- `HttpOnly`
- An appropriate `SameSite` policy
- Restricted path and domain
- Rotation after authentication and security-sensitive transitions

Development relaxations must not carry into remote deployment.

### 5.4 CSRF

All cookie-authenticated state-changing requests require a session-bound CSRF token, including `POST`, `PUT`, `PATCH`, and `DELETE`.

HTMX sends the token through a header such as:

```http
X-CSRF-Token: opaque-token
```

The server validates the session, token, method, and origin policy. An HTMX-specific header is not proof of authenticity. Safe `GET` routes never change state.

### 5.5 Session Expiry

- JSON returns `401` Problem Details.
- HTMX returns `401` plus a safe reauthentication signal or fragment.
- Existing SSE streams close when session validity can no longer be accepted.
- Session expiry does not cancel durable workflow execution.

### 5.6 Authorization

Protected endpoints map to explicit policies such as:

```text
workspace:view
workspace:modify
source:add
source:revoke
workflow:start
workflow:cancel
approval:decide
artifact:view
artifact:export
tool:invoke
configuration:modify
```

Presentation may perform an early check, but the application use case performs the authoritative authorization check. Workers revalidate relevant permissions, source access, approvals, and cancellation before consequential work.

## 6. JSON Representation Conventions

### 6.1 Individual Resources

Individual resources are returned without a universal `data` wrapper.

```json
{
  "id": "0198...",
  "name": "MCP Research",
  "status": "ACTIVE",
  "version": 7,
  "created_at": "2026-08-27T12:00:00Z",
  "links": {
    "self": "/api/v1/workspaces/0198..."
  }
}
```

### 6.2 Collections

```json
{
  "items": [],
  "page": {
    "next_cursor": null,
    "has_more": false,
    "limit": 25
  }
}
```

### 6.3 Shared Rules

- UUIDv7 identifiers are serialized as strings.
- Timestamps use ISO 8601 UTC.
- Stable statuses use uppercase strings.
- Mutable resources expose `version` and an HTTP `ETag`.
- Server-owned lifecycle fields are read-only.
- Fields that do not apply are omitted.
- Applicable fields with no current value use `null`.
- Large content uses dedicated content or download endpoints.
- Useful navigation appears in a modest `links` object.
- Unknown additive fields may be ignored safely.
- Sensitive internal fields are never exposed automatically.

## 7. Resource and Command Semantics

### 7.1 Resource Operations

Use ordinary resource methods for creation, queries, and editable attributes.

```text
GET    /api/v1/workspaces
POST   /api/v1/workspaces
GET    /api/v1/workspaces/{workspace_id}
PATCH  /api/v1/workspaces/{workspace_id}
```

`PATCH` is appropriate for editable metadata such as name, description, title, and ordinary preferences.

### 7.2 Explicit Commands

Use explicit `POST` operations for lifecycle changes, domain transitions, asynchronous work, approvals, and side effects.

```text
POST /api/v1/workflow-runs/{run_id}/cancel
POST /api/v1/workflow-runs/{run_id}/retry
POST /api/v1/approvals/{approval_id}/approve
POST /api/v1/approvals/{approval_id}/reject
POST /api/v1/sources/{source_id}/revoke
POST /api/v1/artifact-versions/{version_id}/export
POST /api/v1/workspaces/{workspace_id}/request-deletion
```

Commands express user intent. The server determines the valid resulting state through domain rules and does not accept arbitrary lifecycle assignments.

## 8. Optimistic Concurrency and Idempotency

### 8.1 Optimistic Concurrency

State-sensitive resources expose an ETag. Clients send `If-Match` when acting on the reviewed version.

```http
If-Match: "7"
```

A mismatch returns `412 Precondition Failed` with current-version information and a refresh action. HTMX returns a safe updated fragment. Stale approvals are never retried silently.

### 8.2 Selective Idempotency

Retry-sensitive, costly, or externally consequential operations accept or require:

```http
Idempotency-Key: 0198...
```

Required examples include:

- Workflow-run creation
- State-changing tool execution
- Artifact export
- Workflow retry
- Upload completion or source registration where network retry could duplicate work
- Future externally consequential actions

The server records user, operation type, scope, canonical request hash, state, result, and retention.

The same key and same canonical request return the existing operation. The same key with a different request returns `409 Conflict`.

### 8.3 Approval Controls

Approval commands require:

- ETag or expected version
- Proposal hash
- Authenticated authorized user
- CSRF token
- Selective idempotency key

Later state-changing execution uses a separate platform execution idempotency identity.

## 9. Problem Details Error Contract

Errors use Problem Details plus platform extensions.

```json
{
  "type": "https://extensible-ai-workspace.local/problems/approval-stale",
  "title": "Approval is no longer current",
  "status": 409,
  "detail": "The approval changed after the page was loaded.",
  "instance": "/api/v1/approvals/0198.../approve",
  "code": "APPROVAL_VERSION_CONFLICT",
  "category": "CONFLICT",
  "correlation_id": "0198...",
  "retry": {
    "allowed": false,
    "strategy": "REFRESH_AND_REVIEW"
  },
  "resource": {
    "type": "approval",
    "id": "0198...",
    "current_version": 5
  }
}
```

Required extensions:

- Stable `code`
- Shared failure `category`
- `correlation_id`

Optional extensions include validation errors, current version, retry guidance, partial-result links, affected resource, remediation, existing idempotent operation, and capability information.

### 9.1 HTTP Status Guidance

- `400`: malformed request
- `401`: no valid session
- `403`: authenticated but unauthorized
- `404`: missing or unavailable resource
- `409`: current domain-state conflict or idempotency-key payload conflict
- `412`: failed `If-Match`
- `413`: request or upload too large
- `415`: unsupported media type
- `422`: structurally valid request fails field or command validation
- `429`: request-rate limit exceeded
- `500`: unexpected defect with safe detail
- `503`: required capability or dependency temporarily unavailable

HTMX errors use the same platform code and recovery semantics but return a safe HTML fragment. Workflow failures after SSE establishment are durable progress events rather than transport `500` responses.

## 10. Asynchronous Operations

Long-running accepted commands return:

```http
202 Accepted
Location: /api/v1/operations/0198...
```

```json
{
  "operation": {
    "id": "0198...",
    "type": "WORKFLOW_START",
    "status": "ACCEPTED",
    "submitted_at": "2026-08-27T12:00:00Z",
    "target": {
      "type": "workflow_run",
      "id": "0198..."
    },
    "status_url": "/api/v1/operations/0198...",
    "events_url": "/events/workflow-runs/0198..."
  },
  "workflow_run": {
    "id": "0198...",
    "status": "CREATED",
    "version": 1
  }
}
```

Operation states are:

```text
ACCEPTED
RUNNING
WAITING_FOR_INPUT
WAITING_FOR_APPROVAL
SUCCEEDED
SUCCEEDED_WITH_LIMITATIONS
FAILED
CANCELLED
RECOVERY_REQUIRED
```

The operation representation may map an existing durable entity, such as a workflow run, source processing run, artifact export, deletion request, or tool execution. A generic database operation entity is not required merely for presentation consistency.

Synchronous operations return `200`, `201`, or `204` as appropriate.

## 11. Pagination, Filtering, and Sorting

Cursor pagination is the default for changing collections. Offset pagination is permitted only for explicitly bounded administrative collections.

A cursor is opaque, tamper-evident, versioned, bound to filters and sorting, and contains no secrets. Stable ordering ends with a unique tie-breaker.

Examples:

- Workflow runs: `created_at DESC, id DESC`
- Messages: `sequence ASC`
- Progress events: `sequence ASC`

Endpoints define default and maximum page size, supported filters, and supported sorting. Excessive requested limits are clamped and the applied limit is returned.

Exact total counts are not included by default. Generic user-defined filter languages are outside the MVP.

## 12. API Versioning

Machine-readable JSON endpoints use major versioning:

```text
/api/v1/...
```

Compatible changes within `v1` include additive optional fields, new endpoints, new filters, new safe enum-like values, new workflows, tools, operations, and error codes.

Breaking changes require a new major version, including removed or renamed fields, changed meaning, newly required fields without defaults, incompatible pagination, authentication, command, or response semantics.

Browser routes do not include an API version. SSE events carry their own event version. Persisted payload, workflow, tool, database, retrieval, and artifact versions remain independent from the API version.

## 13. Workflow and Tool Discovery

### 13.1 Workflow Discovery

```text
GET /api/v1/workflows
GET /api/v1/workflows/{workflow_key}/versions/{version}
```

Descriptors include:

- Key and exact version
- Display name and purpose
- Availability
- Interaction mode
- Required capabilities and configuration
- Versioned bounded input descriptor
- Output types
- Browser specialized-view route where applicable

The generic UI supports bounded input types such as text, long text, Boolean, number, fixed choice, multi-choice, source selection, artifact selection, upload-session reference, URL, and date/time where later needed.

Workflow definitions may register trusted specialized server-rendered views. The JSON descriptor never supplies arbitrary HTML or executable JavaScript.

### 13.2 Tool Discovery

```text
GET /api/v1/tools
GET /api/v1/tools/{tool_id}/versions/{version}
```

Descriptors include stable identity, version, purpose, origin, availability, invocation mode, effect classification, approval requirement, workflow restrictions, schemas, required configuration, timeout, and cancellation support.

Invocation modes are:

- `WORKFLOW_ONLY`
- `DIRECT_ALLOWED`
- `INTERNAL_ONLY`

`INTERNAL_ONLY` tools are omitted from ordinary user discovery. Discovery never exposes credentials, MCP connection strings, secret references, filesystem paths, tokens, or raw internal exceptions.

## 14. Workflow Run Contract

### 14.1 Create Workflow Run

```http
POST /api/v1/workspaces/{workspace_id}/workflow-runs
Idempotency-Key: 0198...
```

```json
{
  "workflow": {
    "key": "research-to-briefing",
    "version": "1.0"
  },
  "conversation_id": "0198...",
  "input": {
    "research_objective": "Compare...",
    "source_ids": ["0198..."]
  },
  "configuration": {
    "retrieval_profile": "default"
  }
}
```

Returns `202 Accepted` with operation and initial workflow-run representations.

### 14.2 Workflow Representation

Exposes:

- Workflow and workspace identity
- Exact workflow version
- Platform lifecycle status
- User-visible stage
- Progress summary
- Pending interaction reference
- Allowed user actions
- Limitations
- Timestamps
- Optimistic concurrency version
- Links to events, approvals, tools, findings, and artifacts

It does not expose worker IDs, leases, checkpoint IDs, graph nodes, raw runtime state, provider credentials, or private reasoning.

### 14.3 Cancel

```http
POST /api/v1/workflow-runs/{run_id}/cancel
If-Match: "8"
Idempotency-Key: 0198...
```

Returns `200` when cancellation is durably complete, `202` when cooperative stopping remains in progress, `409` for invalid state, or `412` for stale version.

### 14.4 Retry

```http
POST /api/v1/workflow-runs/{run_id}/retry
If-Match: "10"
Idempotency-Key: 0198...
```

Clients select only server-advertised recovery actions and never submit internal graph node or checkpoint names.

## 15. Source and Upload Contracts

Source types use separate contracts.

### 15.1 Staged Upload

#### Create session

```http
POST /api/v1/workspaces/{workspace_id}/upload-sessions
```

Request includes filename, media type, byte size, and optional checksum.

#### Upload bytes

```http
PUT /api/v1/upload-sessions/{upload_session_id}/content
```

#### Complete and register

```http
POST /api/v1/upload-sessions/{upload_session_id}/complete
Idempotency-Key: 0198...
```

Completion verifies ownership, expiry, size, checksum, media signature, and state, then finalizes storage, creates the logical source and immutable version, starts processing, and returns `202 Accepted`.

Upload sessions are single-workspace, expiring, immutable after completion, and safely cleanable when abandoned. Filenames are display metadata, not storage keys.

### 15.2 Local Sources

```text
POST /api/v1/workspaces/{workspace_id}/local-source-authorizations
POST /api/v1/workspaces/{workspace_id}/local-file-sources
```

These endpoints exist only when deployment capability supports safe local access. Local-folder requests specify recursive scope and approved exclusions. Arbitrary remote browser paths are never accepted as trusted access.

### 15.3 Web Sources

```text
POST /api/v1/workspaces/{workspace_id}/web-sources
```

Registers the URL and starts asynchronous retrieval and processing.

### 15.4 Revoke and Delete

```text
POST /api/v1/sources/{source_id}/revoke
POST /api/v1/sources/{source_id}/request-deletion
```

Revocation prevents new reads and retrieval while preserving historical provenance. Deletion begins retention and eventual purge.

## 16. Approval Contract

### 16.1 Query

```text
GET /api/v1/workspaces/{workspace_id}/approvals
GET /api/v1/workflow-runs/{run_id}/approvals
GET /api/v1/approvals/{approval_id}
```

The approval representation includes type, semantics, status, version, proposal hash, expiry, safe user-facing proposal, allowed actions, and related links.

### 16.2 Approve

```http
POST /api/v1/approvals/{approval_id}/approve
If-Match: "4"
Idempotency-Key: 0198...
```

```json
{
  "proposal_hash": "sha256:abc123",
  "comment": "Approved for this destination."
}
```

### 16.3 Reject

```http
POST /api/v1/approvals/{approval_id}/reject
If-Match: "4"
Idempotency-Key: 0198...
```

### 16.4 Supersede

Approval types that support user modification may use:

```text
POST /api/v1/approvals/{approval_id}/supersede
```

The original immutable approval is superseded and a new pending approval is created. The server never redirects an approval decision silently to a replacement proposal.

Successful approve or reject returns `200` because the decision is durably complete even if workflow resumption is still pending through post-commit processing.

## 17. Conversation and Message Contract

### 17.1 Conversation Resources

```text
GET  /api/v1/workspaces/{workspace_id}/conversations
POST /api/v1/workspaces/{workspace_id}/conversations
GET  /api/v1/conversations/{conversation_id}
PATCH /api/v1/conversations/{conversation_id}
GET  /api/v1/conversations/{conversation_id}/messages
```

### 17.2 Message Creation

```http
POST /api/v1/conversations/{conversation_id}/messages
Idempotency-Key: 0198...
```

A message contains ordered typed parts and may identify a workflow to start. It returns `201 Created` for synchronous creation or `202 Accepted` when workflow execution begins.

### 17.3 Message Parts

Supported MVP types include:

- `TEXT`
- `SOURCE_REFERENCE`
- `FINDING_REFERENCE`
- `ARTIFACT_REFERENCE`
- `TOOL_EXECUTION_REFERENCE`
- `APPROVAL_REFERENCE`
- `WORKFLOW_REFERENCE`
- `WARNING`
- `LIMITATION_REFERENCE`
- `STRUCTURED_SUMMARY`

Messages link to authoritative resources rather than duplicating full tool results, approval proposals, artifacts, or evidence.

Message states are `PENDING`, `STREAMING`, `COMPLETE`, `INCOMPLETE`, `FAILED`, and `SUPERSEDED`.

Material revision creates a new message linked to the prior message rather than silently overwriting history after consumption.

## 18. Findings and Evidence Contract

```text
GET /api/v1/workflow-runs/{run_id}/findings
GET /api/v1/workspaces/{workspace_id}/findings
GET /api/v1/findings/{finding_id}
GET /api/v1/findings/{finding_id}/evidence
GET /api/v1/artifact-versions/{version_id}/findings
```

Findings expose type, status, canonical text, validation summary, version, timestamps, and links.

Finding types are:

```text
SUPPORTED_FACT
MULTI_SOURCE_SYNTHESIS
RECOMMENDATION
ASSUMPTION
CONFLICT
UNKNOWN
LIMITATION
```

Evidence links expose relationship, validation status, source/version identity, location, bounded excerpt where authorized and available, and protected resource links.

Evidence relationships are:

```text
SUPPORTS
CONTRADICTS
QUALIFIES
PROVIDES_CONTEXT
IDENTIFIES_GAP
```

Validation states are:

```text
PROPOSED
VALIDATED
REJECTED
REQUIRES_REVIEW
UNAVAILABLE
```

Material finding revision uses an explicit revise operation, creates a successor, and requires evidence revalidation. Purged source content returns provenance metadata without an excerpt.

## 19. Tool Execution Contract

### 19.1 Default Behaviour

Tools are workflow-mediated by default. Only `DIRECT_ALLOWED` tools may be directly invoked through public JSON contracts.

### 19.2 Direct Invocation

```http
POST /api/v1/workspaces/{workspace_id}/tool-executions
Idempotency-Key: 0198...
```

A short read-only tool may return `201 Created`. Durable or long-running invocation returns `202 Accepted`. A state-changing direct request creates a proposed execution and first-class approval rather than executing immediately.

All invocations pass through authorization, availability, validation, budgets, effect classification, approval, durable execution records, idempotency, reconciliation, and normalized errors.

## 20. Artifact Contract

### 20.1 Logical Artifact

```text
GET /api/v1/artifacts/{artifact_id}
```

Returns logical metadata and current-version reference.

### 20.2 Immutable Version

```text
GET /api/v1/artifacts/{artifact_id}/versions/{version_id}
```

Returns version number, media type, size, checksum, status, generation policy, related findings/manifests, and content/download/export links.

### 20.3 Content and Preview

```text
GET /api/v1/artifact-versions/{version_id}/content
GET /app/artifact-versions/{version_id}/preview
```

Content is authorized. Browser previews sanitize untrusted content and never execute scripts, external embedded resources, or HTMX attributes from artifact text.

### 20.4 Download

```text
GET /api/v1/artifact-versions/{version_id}/download
```

Streams authorized content with a safe filename. Storage paths, object keys, and backend URLs remain hidden.

### 20.5 Export

```http
POST /api/v1/artifact-versions/{version_id}/export
If-Match: "3"
Idempotency-Key: 0198...
```

The request provides a platform-issued destination reference, filename, overwrite policy, approval ID, and proposal hash. Export returns `202 Accepted` with operation and export resources.

Artifact creation inside managed storage and approved external export are separate operations.

## 21. Workspace Deletion Contract

```http
POST /api/v1/workspaces/{workspace_id}/request-deletion
If-Match: "12"
Idempotency-Key: 0198...
```

Returns `202 Accepted` with an operation and deletion-request resource.

User-facing deletion states are:

```text
REQUESTED
RETAINED
PURGE_SCHEDULED
PURGING
PURGED
FAILED
CANCELLED
```

During retention, new messages, sources, workflows, and approvals are prohibited. Where recovery is configured, deletion may be cancelled before purge through an explicit command. Restore never restarts workflows, revives expired approvals, or assumes source access remains valid.

## 22. SSE Contract

### 22.1 Stream

```text
GET /events/workflow-runs/{run_id}
```

The session is authenticated and access to the workflow is authorized.

### 22.2 Event Families

```text
workflow.lifecycle
workflow.stage
workflow.progress
output.snapshot
tool.lifecycle
approval.required
approval.resolved
artifact.available
operation.warning
operation.failed
stream.reset
```

Events use a common envelope containing durable per-run sequence in the SSE `id`, stable event family, event version, workflow-run ID, occurrence timestamp, lifecycle/stage where relevant, small payload, and links to full resources.

Workflow-specific detail is namespaced and versioned. Clients may ignore detail they do not understand while continuing to process known platform event families.

### 22.3 Reconnection

Clients reconnect using:

```http
Last-Event-ID: 47
```

The server reauthenticates, reauthorizes, validates the cursor, returns later durable events, and resumes streaming.

If the cursor is no longer retained, `stream.reset` provides the current sequence and state URL. Clients refresh authoritative state rather than reconstructing missing history.

### 22.4 Heartbeats

Protocol heartbeats are not durable events, do not increment workflow sequence, and do not imply workflow progress.

### 22.5 Failures

Connection-establishment errors use HTTP and Problem Details. Workflow failures after establishment use durable workflow events. Browser disconnection does not cancel the workflow or lose progress.

### 22.6 Polling Fallback

```text
GET /api/v1/workflow-runs/{run_id}
GET /api/v1/workflow-runs/{run_id}/progress-events
```

Polling and SSE expose the same authoritative state semantics.

## 23. Health, Readiness, and Capability Status

### 23.1 Liveness

```text
GET /health/live
```

Returns minimal process-alive status.

### 23.2 Readiness

```text
GET /health/ready
```

Returns minimal role readiness. `503` indicates the runtime cannot safely perform its assigned role.

### 23.3 Authenticated Capability Status

```text
GET /api/v1/capabilities
```

Returns safe status for workflows, tools, providers, local source support, uploads, SSE, and visible limits. Optional capability unavailability does not make the endpoint fail.

Public health endpoints never expose dependency addresses, topology, secrets, provider details, exception messages, or internal tool configuration.

## 24. Rate Limits and Resource Controls

The API applies layered controls:

- Deployment-wide request, connection, upload, queue, worker, and provider concurrency
- Authenticated-user limits
- Endpoint-class policies
- Security-sensitive endpoint controls
- SSE connection and reconnection limits
- Upload-session, byte, and temporary-storage limits
- Durable workflow budgets after acceptance

In-process counters may support low-risk short-window limits for the single-web-runtime MVP. Correctness-sensitive quotas use PostgreSQL state. Redis is not required initially.

HTTP rate-limit failures return `429`, `Retry-After` where meaningful, and Problem Details. Workflow-budget exhaustion is reported through durable workflow state and progress events rather than retroactively changing the accepted HTTP request.

Upload failures use `413`, `415`, or `422` as appropriate and never activate an invalid source.

## 25. HTMX Interaction Specification

HTMX routes use shared application use cases and follow these conventions:

- Full pages and fragments are separate response intents.
- State-changing requests require CSRF.
- Validation failures return safe fragments for the affected region.
- Stale ETags return refreshed resource or approval fragments and require renewed review.
- Session expiry returns `401` with a reauthentication signal rather than a login page inserted with `200`.
- SSE events may trigger fragment refresh through resource URLs.
- Critical forms retain standard server-rendered behaviour where practical.
- Untrusted message, source, artifact, and evidence content is escaped or sanitized.
- Workflow-specific views reuse the stable workspace shell and generic approval, progress, tool, artifact, and error components.

HTMX fragment structure is an internal presentation contract and is not part of `/api/v1` compatibility guarantees.

## 26. OpenAPI and Supplementary Specifications

### 26.1 Generated OpenAPI

OpenAPI covers JSON HTTP contracts, including:

- `/api/v1` endpoints
- Request and response schemas
- Session and CSRF requirements
- Problem Details
- Collection and operation envelopes
- Pagination and filters
- ETag and idempotency behaviour
- Upload sessions
- Content and downloads
- Relevant health endpoints
- Stable operation identifiers
- Deprecation metadata

FastAPI-generated OpenAPI is treated as a public contract, not incidental output.

### 26.2 Supplementary Contracts

Separate focused specifications document:

- SSE event families, envelope, reconnection, heartbeats, reset, and compatibility
- HTMX fragment, validation, target, redirect, session-expiry, stale-state, and accessibility conventions
- Internal Python ports, adapters, and conformance test suites

OpenAPI is not forced to describe dynamic browser replacement behaviour inaccurately.

## 27. Contract Testing

### 27.1 OpenAPI

- Validate generated specification.
- Verify required paths, operation identifiers, security, requests, responses, and Problem Details.
- Compare against the accepted baseline in CI.
- Detect removed endpoints/fields, new required fields, narrowed values, changed statuses, and changed authentication.

### 27.2 JSON Endpoints

Test success, authentication, authorization, validation, ETag conflicts, idempotent replay, key-payload conflicts, invalid transitions, unavailable capabilities, rate limits, and missing resources.

### 27.3 SSE

Test ordering, `Last-Event-ID`, reset, authorization, unknown workflow detail, heartbeats, durable failures, session revocation, and polling consistency.

### 27.4 HTMX

Test correct fragments and targets, validation rendering, CSRF, stale approval refresh, authentication expiry, redirects, sanitization, and progressive enhancement.

### 27.5 Uploads

Test ownership, expiry, limits, media validation, checksum mismatch, duplicate completion, idempotent registration, partial failure, and temporary cleanup.

### 27.6 Approvals

Test ETag mismatch, proposal mismatch, expiry, supersession, duplicate submission, authorization, changed workflow state, execution binding, and rejection with no external effect.

### 27.7 Consumer Focus

The HTMX browser is the first consumer and must use the same shared application semantics rather than undocumented shortcuts. Future machine clients add consumer tests against `/api/v1`.

## 28. API Compatibility Rules

Within `/api/v1`:

- Additive optional fields are allowed.
- Unknown additive fields may be ignored.
- Stable codes and meanings are not reused incompatibly.
- Existing required fields are not removed or renamed.
- Optional fields do not become required without a compatible default.
- Commands do not change from synchronous to asynchronous without compatible transition.
- Authentication and pagination semantics remain stable.
- New enum-like values require safe client fallback and deliberate review.

A future `v2` receives migration notes, deprecation metadata, and a defined transition period where practical.

## 29. Security Guardrails

- No state change through `GET`.
- No raw storage paths or object keys in public contracts.
- No client-controlled authoritative lifecycle status.
- No direct browser authority over approvals, tools, jobs, or workflow execution.
- No arbitrary server filesystem paths from remote clients.
- No provider tokens, session tokens, secrets, complete claims, stack traces, or private reasoning in responses.
- No message, evidence, artifact, or source content interpreted as executable interface instructions.
- No automatic invocation merely because a tool is discoverable.
- No silent approval redirection to superseded proposals.
- No silent retry of uncertain state-changing actions.
- No request limit or workflow budget increase without configured authorization.

## 30. Principal Research-to-Briefing API Sequence

1. Establish local or OIDC application session.
2. Create or open a workspace.
3. Create a conversation if required.
4. Create upload sessions, register web sources, or authorize supported local sources.
5. Monitor source-processing operations.
6. Discover the exact Research-to-Briefing workflow version.
7. Create a workflow run with idempotency key.
8. Receive `202 Accepted`, operation, run, status, and SSE links.
9. Follow SSE or poll current state.
10. Retrieve and decide any first-class web-research approval using ETag and proposal hash.
11. Review generated message, findings, evidence, and artifact-version resources.
12. Retrieve sanitized preview or authorized artifact content.
13. Retrieve the export approval proposal.
14. Approve the exact proposal.
15. Submit the export command with approval, ETag, proposal hash, and idempotency key.
16. Monitor the export operation.
17. Reopen the workspace and retrieve the durable conversation, workflow, findings, approvals, and artifacts.

## 31. Consistency Review

The API contract is consistent with the PRD, HLA, TDD, and Data Design Document:

- The HTMX interface remains lean while sharing application use cases with JSON and SSE adapters.
- The API exposes platform lifecycle and user-meaningful stages without leaking worker or LangGraph internals.
- First-class sources, approvals, findings, artifacts, and operations preserve the durable data model.
- Reviewable proposal versions and hashes protect consequential actions.
- Cursor pagination, ETags, idempotency, rate limits, and operations support changing durable workflows.
- Workflow and tool discovery supports future non-research capabilities without building a no-code UI framework.
- Session authentication fits the MVP while future machine authentication remains additive.
- Source uploads, artifact exports, and deletion use staged asynchronous contracts.
- SSE remains lightweight, durable, reconnectable, and workflow-extensible.
- Problem Details and contract tests provide stable failure and compatibility behaviour.
- No accepted requirement conflict was identified.

## 32. Deferred Decisions

- Exact endpoint names where implementation conventions suggest minor refinements
- Concrete Pydantic models and OpenAPI operation IDs
- Exact default and maximum page sizes
- Cursor encoding and signing approach
- Session and CSRF libraries
- Exact API-level status mappings
- Rate-limit values and storage implementation
- SSE batching, heartbeat, and retention values
- Upload-session expiry and byte limits
- Direct-upload support for future object storage
- Machine authentication and scopes
- Content-range support
- Interactive documentation exposure policy
- OpenAPI compatibility-checking tool
- Full endpoint inventory for post-MVP workflows

## 33. Definition of Completion

This API Contract is complete when it provides enough stable transport, resource, command, error, streaming, security, concurrency, idempotency, pagination, discovery, and compatibility rules to implement the HTMX browser and `/api/v1` without exposing internal execution or persistence details.
