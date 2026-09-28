# Extensible AI Workspace

Extensible AI Workspace is an open-source, self-hostable AI workspace for technically capable individual users.

The project is currently in its initial implementation stage. The approved architecture documents are the authoritative baseline for implementation.

## Requirements

- Python 3.14
- uv

## Local setup

Create or synchronize the project environment:

## Runtime roles

The application runs in one of two explicit runtime roles:

- `web`: Handles interactive application requests and presentation.
- `worker`: Handles long-running and resource-intensive work.

Select the runtime role using the required `AIW_RUNTIME_ROLE` environment variable.

## Web runtime

Start the web runtime:

```bash
AIW_RUNTIME_ROLE=web uv run extensible-ai-workspace
```

The web server listens locally at `http://127.0.0.1:8000`.

Available routes:

- `/app`: Minimal server-rendered application page.
- `/health/live`: Reports whether the web process is alive and responding.
- `/health/ready`: Reports whether the web runtime can safely perform its current responsibilities.

The liveness endpoint does not check external dependencies. The readiness endpoint returns HTTP 503 when a required dependency is unavailable.

PostgreSQL readiness is not connected yet. It will replace the current in-process readiness check when the local runtime foundation is implemented.


## Local container environment

The local environment contains three services:

- `postgres`: PostgreSQL database and authoritative application dependency.
- `web`: FastAPI web runtime.
- `worker`: Independent worker runtime using the same application image.

Build and start the environment:

```bash
docker compose up --build --detach

Inspect all services:
docker compose ps --all

The expected state is:
- PostgreSQL is running and healthy.
- The web runtime is running.
- The worker runtime is running.

Open the application at http://127.0.0.1:8000/app.

Verify liveness:
curl --fail --silent --show-error \
  http://127.0.0.1:8000/health/live

Verify readiness:
curl --fail --silent --show-error \
  http://127.0.0.1:8000/health/ready
Readiness includes a PostgreSQL connectivity check. If PostgreSQL is unavailable, liveness remains successful while readiness returns HTTP 503.

View service logs:
docker compose logs web
docker compose logs worker
docker compose logs postgres

Stop and remove the containers:
docker compose down

The PostgreSQL named volume is preserved by the normal shutdown command. To delete local database data intentionally, use:
docker compose down --volumes

The worker currently validates PostgreSQL and then remains idle. It does not claim jobs or execute workflows.


## Database migrations

Database schema changes are managed through Alembic. The web and worker
runtimes do not apply migrations automatically.

Apply all pending migrations:

```bash
docker compose \
  --profile tools \
  run \
  --rm \
  --build \
  migrate
```

The migration service waits for PostgreSQL to become healthy, applies all
migrations through the current Alembic head revision, and exits.

View the current migration revision:

```bash
docker compose exec -T postgres \
  psql \
  --username app \
  --dbname extensible_ai_workspace \
  --tuples-only \
  --command \
  "SELECT version_num FROM alembic_version;"
```

The application currently supports schema revision `0001`. Web readiness and
worker startup fail safely when the database is unavailable, has no applied
revision, or has an unsupported revision.

Generate migration SQL without applying it:

```bash
AIW_DATABASE_URL=postgresql://app:development@postgres:5432/extensible_ai_workspace \
uv run alembic upgrade head --sql
```

Downgrades are intended for isolated development and integration testing.
Do not downgrade a database containing data that must be preserved without
first reviewing the migration and preparing an appropriate recovery plan.

## PostgreSQL integration tests

Migration integration tests use a separate, disposable PostgreSQL service.
The test database is published only to the local host at
`127.0.0.1:5433`.

Start the test database:

```bash
docker compose \
  --profile test \
  up \
  --detach \
  --wait \
  postgres_test
```

Run the migration integration test:

```bash
uv run pytest \
  -m integration \
  tests/test_migrations_integration.py
```

The test creates a uniquely named temporary database, upgrades it to the
current migration head, verifies the expected schema, downgrades it to the
base revision, and deletes it.

Stop and remove the disposable test database:

```bash
docker compose \
  --profile test \
  stop \
  postgres_test

docker compose \
  --profile test \
  rm \
  --force \
  postgres_test
```

The normal application database and its named volume are not used by the
migration integration test.

## Trusted-local authentication

The local container environment uses explicitly enabled trusted-local
authentication. This mode is intended only for a loopback-accessible local
deployment.

The application requires:

```text
AIW_AUTHENTICATION_MODE=local_trusted
AIW_PUBLIC_ORIGIN=http://127.0.0.1:8000
AIW_LOCAL_IDENTITY_ISSUER=extensible-ai-workspace-local
AIW_LOCAL_IDENTITY_SUBJECT=local-user
AIW_LOCAL_IDENTITY_DISPLAY_NAME=Local User
```

Trusted-local authentication fails configuration validation when the public
origin is not a loopback address.

Establish a local application session:

```bash
COOKIE_JAR=/tmp/aiw-auth-cookies.txt
rm -f "$COOKIE_JAR"

LOGIN_RESPONSE=$(
  curl --silent \
    --cookie-jar "$COOKIE_JAR" \
    http://127.0.0.1:8000/auth/login
)
```

The browser receives an opaque `HttpOnly` session cookie. PostgreSQL stores
only the SHA-256 hash of the session token.

Extract the session-bound CSRF token from the one-time login response:

```bash
CSRF_TOKEN=$(
  printf '%s' "$LOGIN_RESPONSE" |
  uv run python -c \
    'import json, sys; print(json.load(sys.stdin)["csrf_token"])'
)
```

Inspect the current session:

```bash
curl --silent \
  --cookie "$COOKIE_JAR" \
  http://127.0.0.1:8000/auth/session
```

Session inspection returns safe identity and expiry metadata. It does not
return the session token, session-token hash, raw CSRF token, or stored CSRF
verifier.

Logout requires the session cookie, matching public origin, and session-bound
CSRF token:

```bash
curl --silent \
  --cookie "$COOKIE_JAR" \
  --header "Origin: http://127.0.0.1:8000" \
  --header "X-CSRF-Token: $CSRF_TOKEN" \
  --request POST \
  http://127.0.0.1:8000/auth/logout
```

Logout revokes the server-side session and clears the browser cookie.

Remove temporary credential material:

```bash
unset LOGIN_RESPONSE CSRF_TOKEN
rm -f "$COOKIE_JAR"
```

## Workspace application capability

The Workspace module owns workflow-neutral workspace lifecycle and
persistence.

The current application capability supports:

- Creating an active workspace for an authenticated internal user
- Retrieving an active workspace by workspace ID and owner user ID
- Listing an owner's active workspaces
- Returning workspaces in stable newest-first order
- Persisting workspaces through an application-controlled Unit of Work

Workspace creation accepts only:

- Authenticated owner user ID
- Workspace name
- Optional description

The application controls:

- Workspace ID
- Initial status
- Creation and update timestamps
- Lifecycle timestamps
- Optimistic concurrency version

Workspace names are trimmed and cannot be blank. Optional descriptions are
trimmed, and blank descriptions are stored as `NULL`.

Workspace retrieval is owner-scoped. The application returns the same
unavailable result when a workspace:

- Does not exist
- Belongs to another user
- Is not active

This prevents callers from using different application outcomes to discover
another user's workspace.

Workspace listings use the stable ordering:

```text
created_at descending
id descending
```

The identifier provides a deterministic tie-breaker when multiple workspaces
have the same creation timestamp.

The current capability is implemented below the presentation layer. Browser
routes, forms, redirects, CSRF handling for workspace creation, and
server-rendered workspace pages are implemented separately.
