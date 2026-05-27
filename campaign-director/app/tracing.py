import os
import sys


def setup_telemetry():
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if not endpoint:
        return
    try:
        os.environ["MLFLOW_TRACKING_URI"] = "file:///tmp/mlruns"
        os.environ.setdefault("MLFLOW_ENABLE_ASYNC_LOGGING", "false")

        import mlflow
        experiment = os.environ.get("MLFLOW_EXPERIMENT_NAME", "marketing-assistant")
        mlflow.set_experiment(experiment)

        try:
            mlflow.langchain.autolog(run_tracer_inline=True)
            print("[tracing] mlflow.langchain.autolog enabled", file=sys.stderr)
        except Exception as e:
            print(f"[tracing] langchain autolog failed: {e}", file=sys.stderr)

        print(f"[tracing] MLflow tracing → OTLP {endpoint}", file=sys.stderr)
    except Exception as e:
        print(f"[tracing] init failed: {e}", file=sys.stderr)
