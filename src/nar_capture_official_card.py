"""Capture raw official card; never assert race identity or pre-start validity."""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from nar_race_request import resolve

MAX_BYTES = 8 * 1024 * 1024

def capture(request, day, output, opener=urlopen):
    target = resolve(request, day)
    if target["model"] != "nar_flat":
        raise ValueError("BANEI_REQUIRES_SEPARATE_MODEL")
    started = time.monotonic()
    with opener(Request(target["card_url"], headers={"User-Agent":"NARResearch/1.0"}), timeout=20) as response:
        if response.status != 200 or urlsplit(response.geturl()).hostname != "www.keiba.go.jp":
            raise ValueError("unexpected response")
        if response.headers.get_content_type() != "text/html":
            raise ValueError("unexpected content type")
        raw = response.read(MAX_BYTES + 1)
        if not raw or len(raw) > MAX_BYTES:
            raise ValueError("invalid response size")
        final_url = response.geturl()
    digest = hashlib.sha256(raw).hexdigest()
    manifest = {"request":target,"final_url":final_url,"sha256":digest,
                "bytes":len(raw),"captured_at":datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds":time.monotonic()-started,
                "status":"RAW_CAPTURE_UNVERIFIED"}
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (digest+".html")).write_bytes(raw)
    (directory / (digest+".json")).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("request")
    p.add_argument("--date")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(capture(a.request,a.date,a.output),ensure_ascii=False))
