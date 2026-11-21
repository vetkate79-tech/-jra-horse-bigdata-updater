#!/usr/bin/env python3
"""Acquire a real NAR race card and archive its raw evidence; never invent horse history.

A fetch or parser failure is an explicit failure, not a successful prediction.
This probe does not promote historical web pages to a pre-race sealed snapshot.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts=[]
    def handle_data(self, data):
        t=" ".join(data.split())
        if t:self.parts.append(t)

def collect(url, output):
    if not url.startswith("https://keiba.rakuten.co.jp/race_card/list/"):
        raise ValueError("only Rakuten NAR race card is supported by this probe")
    req=Request(url,headers={"User-Agent":"Mozilla/5.0 (compatible; NARResearchAudit/1.0)"})
    with urlopen(req,timeout=25) as response:
        raw=response.read(8_000_001)
        if len(raw)>8_000_000:raise ValueError("oversized response")
        charset=response.headers.get_content_charset() or "utf-8"
    text=raw.decode(charset,errors="replace")
    parser=TextExtractor()
    parser.feed(text)
    names=["クラックオブドーン","ミラクルドリーム","ヒマワリクン","ビックス","ファストワン","ウォーターレモン","ユキノマリア","ストーミーデイ","マイネルフォーコン","ムサシフウジン","ブルグミューラー"]
    found=[n for n in names if n in text]
    audit={"source_url":url,"retrieved_at":datetime.now(timezone.utc).isoformat(),
           "sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),
           "found_runners":found,"found_count":len(found),
           "status":"RAW_EVIDENCE_ONLY_NOT_PRE_RACE_SEALED",
           "notes":"No scores generated; post-start retrieval cannot establish pre-start availability."}
    out=Path(output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.with_suffix(".html").write_bytes(raw)
    out.with_suffix(".txt").write_text("\n".join(parser.parts),encoding="utf-8")
    out.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(audit,ensure_ascii=False))
    if len(found)!=11:raise ValueError("race card did not contain all 11 runners")
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--url",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    collect(a.url,a.output)
