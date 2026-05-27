import os
import sys
from contextvars import ContextVar

_trace_headers: ContextVar[dict] = ContextVar("_trace_headers", default={})


def get_trace_headers() -> dict:
    return _trace_headers.get({})


class TraceContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = {}
            for k, v in scope.get("headers", []):
                name = k.decode("latin-1") if isinstance(k, bytes) else k
                if name in ("traceparent", "tracestate"):
                    headers[name] = v.decode("latin-1") if isinstance(v, bytes) else v
            token = _trace_headers.set(headers)
            try:
                await self.app(scope, receive, send)
            finally:
                _trace_headers.reset(token)
        else:
            await self.app(scope, receive, send)


def setup_telemetry():
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if not endpoint:
        return
    try:
        os.environ["MLFLOW_TRACKING_URI"] = "file:///tmp/mlruns"

        import mlflow
        experiment = os.environ.get("MLFLOW_EXPERIMENT_NAME", "marketing-assistant")
        mlflow.set_experiment(experiment)

        print(f"[tracing] MLflow tracing → OTLP {endpoint}", file=sys.stderr)
    except Exception as e:
        print(f"[tracing] init failed: {e}", file=sys.stderr)
