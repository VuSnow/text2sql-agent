"""Smoke test the FastAPI health endpoint.

Usage:
    AGENT_BASE_URL="http://127.0.0.1:8001" \
    conda run -n eog-agent python tests/manual/test_agent_health_smoke.py
"""

import json
import os
from urllib.request import urlopen


def main() -> None:
    base_url = os.getenv("AGENT_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
    with urlopen(f"{base_url}/health", timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()