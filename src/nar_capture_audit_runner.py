"""Capture and audit in one invocation; never authorize predictions."""
import argparse
import json
import time
from pathlib import Path
from nar_capture_official_card import capture
from nar_audit_capture import audit

def execute(request, day, output, opener=None):
    started = time.monotonic()
    kwargs = {} if opener is None else {"opener": opener}
    manifest = capture(request, day, output, **kwargs)
    verified = audit(Path(output) / (manifest["sha256"] + ".json"))
    if verified["status"] != "RAW_INTEGRITY_VERIFIED_BODY_UNVERIFIED":
        raise ValueError("unexpected audit status")
    return {**verified, "elapsed_seconds": time.monotonic()-started,
            "prediction_allowed": False, "next_gate": "BODY_IDENTITY_AND_HISTORY"}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("request")
    p.add_argument("--date")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    print(json.dumps(execute(a.request, a.date, a.output), ensure_ascii=False))
