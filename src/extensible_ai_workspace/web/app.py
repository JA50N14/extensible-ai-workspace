"""FastAPI application construction."""

from fastapi import FastAPI, Response, status
from fastapi.responses import HTMLResponse

from extensible_ai_workspace.web.readiness import (
    ReadinessCheck,
    default_readiness_check,
)


def create_app(
    readiness_check: ReadinessCheck = default_readiness_check,
) -> FastAPI:
    """Construct the web application."""

    app = FastAPI(title="Extensible AI Workspace")

    @app.get("/health/live")
    def liveness() -> dict[str, str]:
        """Report whether the web process can respond."""

        return {"status": "alive"}

    @app.get("/health/ready")
    def readiness(response: Response) -> dict[str, str]:
        """Report whether the web runtime can operate safely."""

        if not readiness_check():
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready"}

        return {"status": "ready"}

    @app.get("/app", response_class=HTMLResponse)
    def application_page() -> str:
        """Render the minimal application page."""

        return """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Extensible AI Workspace</title>
          </head>
          <body>
            <main>
              <h1>Extensible AI Workspace</h1>
              <p>The web runtime is running.</p>
            </main>
          </body>
        </html>
        """

    return app


app = create_app()
