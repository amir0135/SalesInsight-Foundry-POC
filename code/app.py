"""
This module contains the entry point for the application.
"""

import os
import logging
import socket

# Workaround: macOS mDNSResponder cannot resolve .search.windows.net CNAME chain
# through corporate DNS (207.46.216.45). Pre-resolve and cache via subprocess.
_SEARCH_HOST = os.getenv("AZURE_SEARCH_SERVICE", "")
if _SEARCH_HOST:
    import subprocess
    import re
    from urllib.parse import urlparse

    _parsed = urlparse(_SEARCH_HOST)
    _hostname = _parsed.hostname or _SEARCH_HOST
    try:
        _result = subprocess.run(
            ["dig", "+short", _hostname],
            capture_output=True, text=True, timeout=10
        )
        _lines = _result.stdout.strip().split("\n")
        _ip = None
        for _line in reversed(_lines):
            if re.match(r"^\d+\.\d+\.\d+\.\d+$", _line.strip()):
                _ip = _line.strip()
                break
        if _ip:
            _orig_getaddrinfo = socket.getaddrinfo

            def _patched_getaddrinfo(host, port, *args, **kwargs):
                if host == _hostname:
                    return _orig_getaddrinfo(_ip, port, *args, **kwargs)
                return _orig_getaddrinfo(host, port, *args, **kwargs)

            socket.getaddrinfo = _patched_getaddrinfo
            import sys
            print(f"DNS workaround active: {_hostname} -> {_ip}", file=sys.stderr, flush=True)
    except Exception:
        pass  # Fall back to normal resolution

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

logging.captureWarnings(True)

# Logging configuration from environment variables
AZURE_BASIC_LOGGING_LEVEL = os.environ.get("LOGLEVEL", "INFO")
PACKAGE_LOGGING_LEVEL = os.environ.get("PACKAGE_LOGGING_LEVEL", "WARNING")
AZURE_LOGGING_PACKAGES = os.environ.get("AZURE_LOGGING_PACKAGES", "")
AZURE_LOGGING_PACKAGES = [pkg.strip() for pkg in AZURE_LOGGING_PACKAGES if pkg.strip()]

# Configure logging levels from environment variables
logging.basicConfig(
    level=getattr(logging, AZURE_BASIC_LOGGING_LEVEL.upper(), logging.INFO)
)

# Configure Azure package logging levels
azure_package_log_level = getattr(
    logging, PACKAGE_LOGGING_LEVEL.upper(), logging.WARNING
)
for logger_name in AZURE_LOGGING_PACKAGES:
    logging.getLogger(logger_name).setLevel(azure_package_log_level)

# We cannot use EnvHelper here as Application Insights should be configured first
# for instrumentation to work correctly
if os.getenv("APPLICATIONINSIGHTS_ENABLED", "false").lower() == "true":
    configure_azure_monitor()
    HTTPXClientInstrumentor().instrument()  # httpx is used by openai

# pylint: disable=wrong-import-position
from create_app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run()
