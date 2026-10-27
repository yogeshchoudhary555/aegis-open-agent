"""Env-based configuration. No secrets in code — everything comes from env vars.

Live connections (all optional; unset = demo mode):
  ZETARIS_BASE_URL   Base URL of a Zetaris REST service, e.g. http://localhost:8888
  ZETARIS_API_KEY    Bearer token for that Zetaris service (if it requires one)
  ZETARIS_QUERY_PATH Query route on that service, e.g. /api/query.
                     No default is assumed: Zetaris deployments differ, so if
                     ZETARIS_BASE_URL is set without a path, the client raises
                     a clear config error instead of guessing an endpoint.
  METERLESS_BASE_URL OpenAI-compatible base URL of a locally run model
                     endpoint (e.g. a Meterless Nightshift instance, if it
                     exposes one). Used as the "power" lane backend.
  NVIDIA_API_KEY     Key for build.nvidia.com (free tier) — NVIDIA Nemotron
                     via the OpenAI-compatible endpoint
                     https://integrate.api.nvidia.com/v1
  NEBIUS_API_KEY     Key for Nebius Token Factory — NVIDIA Nemotron via
                     https://api.tokenfactory.nebius.com/v1
  NEMOTRON_MODEL     Model id for the live backends
                     (default: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B)
"""
import os


def _load_dotenv(path=".env"):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass


_load_dotenv()

ZETARIS_BASE_URL = os.environ.get("ZETARIS_BASE_URL", "")
ZETARIS_API_KEY = os.environ.get("ZETARIS_API_KEY", "")
ZETARIS_QUERY_PATH = os.environ.get("ZETARIS_QUERY_PATH", "")
METERLESS_BASE_URL = os.environ.get("METERLESS_BASE_URL", "")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NEBIUS_API_KEY = os.environ.get("NEBIUS_API_KEY", "")
NEBIUS_BASE_URL = os.environ.get(
    "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1"
)
NEMOTRON_MODEL = os.environ.get(
    "NEMOTRON_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
)
PORT = int(os.environ.get("PORT", "8000"))


def data_mode() -> str:
    """'zetaris' when a live Zetaris endpoint is configured, else 'demo'."""
    return "zetaris" if ZETARIS_BASE_URL else "demo"


def power_mode() -> str:
    """First configured live model backend, else 'demo'."""
    if METERLESS_BASE_URL:
        return "meterless"
    if NVIDIA_API_KEY:
        return "nvidia"
    if NEBIUS_API_KEY:
        return "nebius"
    return "demo"
