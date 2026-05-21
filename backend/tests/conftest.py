"""Test-wide setup: disable real tracing so no spans are exported to Phoenix.

The OpenTelemetry no-op tracer keeps ``@traced`` working without a collector.
"""

import os

os.environ.setdefault("DISABLE_TRACING", "1")
