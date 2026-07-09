"""
Selects the backend implementation once, at import time:

- STANDALONE_MODE=true (or 1/yes/on)  -> in-process engine (local_engine)
- STANDALONE_MODE=false (or 0/no/off) -> FastAPI client (api_client)
- unset -> standalone if API_BASE_URL is also unset, client otherwise.

The default rule means Docker deployments (which set API_BASE_URL in
docker-compose.yml) automatically get full GraphRAG client mode, while
Streamlit Community Cloud (no backend, no API_BASE_URL) automatically gets
standalone mode with zero configuration.

Pages import `api` from here and never know which mode they're in.
"""
import os


def is_standalone() -> bool:
    flag = os.environ.get("STANDALONE_MODE", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    return not os.environ.get("API_BASE_URL")


if is_standalone():
    import local_engine as api  # noqa: F401
else:
    import api_client as api  # noqa: F401
