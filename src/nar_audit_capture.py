"""Audit raw capture integrity, not race body identity or pre-start eligibility."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from datetime import datetime
from nar_race_request import resolve

def audit(manifest_path):
    path = Path(manifest_path)
    m = json.loads(path.read_text(encoding="utf-8"))
    if m["status"] != "RAW_CAPTURE_UNVERIFIED":
        raise ValueError("unexpected capture status")
    t = m["request"]
    expected = resolve(t["track"] + str(t["race_no"]), t["date"])
    if t != expected or t["model"] != "nar_flat":
        raise ValueError("request mismatch")
    actual, wanted = urlsplit(m["final_url"]), urlsplit(expected["card_url"])
    if (actual.scheme, actual.netloc, actual.path, parse_qs(actual.query)) != (wanted.scheme, wanted.netloc, wanted.path, parse_qs(wanted.query)):
        raise ValueError("redirect identity mismatch")
    digest = m["sha256"]
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or path.stem != digest:
        raise ValueError("invalid digest")
    raw = path.with_suffix(".html").read_bytes()
    if not raw or len(raw) != m["bytes"] or hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("raw integrity failure")
    if datetime.fromisoformat(m["captured_at"]).utcoffset() is None:
        raise ValueError("capture time missing timezone")
    return {"status":"RAW_INTEGRITY_VERIFIED_BODY_UNVERIFIED","request":expected,"sha256":digest}
