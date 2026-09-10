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

