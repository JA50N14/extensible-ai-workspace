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

Start the web runtime:

```bash
AIW_RUNTIME_ROLE=web uv run extensible-ai-workspace
