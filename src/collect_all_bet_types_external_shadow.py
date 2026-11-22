#!/usr/bin/env python3
"""Experimental read-only race-specific external odds fetch. No production writes.

Quote extraction is intentionally strict. An unrecognized layout means NO_QUOTE.
"""
import json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup

OUT = Path("shadow-artifacts/all_bet_types_external_quotes.json")
SEALED = Path("docs/data/live_predictions_sealed.json")
PATHS = {"WIDE": "wide", "QUINELLA": "ur", "EXACTA": "ut",
         "TRIO": "fuku3", "TRIFECTA": "st"}
# Verified Yahoo race code from published race URLs; not inferred for other races.
KNOWN_RACE_CODES = {("2026-11-22", "京都", 10): "2608050610"}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=12) as res:
        return res.read().decode("utf-8", "replace")

def extract(html, kind, runners):
    """Only accept one complete ticket and one explicitly odds-labelled cell per row."""
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    need = 3 if kind in ("TRIO", "TRIFECTA") else 2
    for tr in soup.select("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        ticket = None
        price = None
        for cell in cells:
            txt = " ".join(cell.stripped_strings)
            cls = " ".join(cell.get("class", [])).lower()
            if ("odds" in cls or "rate" in cls) and re.fullmatch(r"\\d{1,4}(?:\\.\\d+)?", txt):
                price = float(txt)
            # Reject ambiguous rows; all horse numbers must occur together in one cell.
            if re.fullmatch(r"\\d{1,2}(?:\\s*[-－→>]\\s*\\d{1,2}){" + str(need - 1) + r"}", txt):
                numbers = re.findall(r"\\d{1,2}", txt)
                if len(set(numbers)) == need and all(str(int(n)) in runners for n in numbers):
                    if kind in ("WIDE", "QUINELLA", "TRIO"):
                        numbers.sort(key=int)
                    candidate = "-".join(str(int(n)) for n in numbers)
                    if ticket is not None and ticket != candidate:
                        ticket = None
                        break
                    ticket = candidate
        if ticket and price is not None and price >= 1.0:
            found[ticket] = price
    return found

def main():
    sealed = json.loads(SEALED.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for race in sealed.get("races", []):
        key = (race.get("date"), race.get("track"), int(race.get("race_no") or 0))
        code = KNOWN_RACE_CODES.get(key)
        if not code:
            continue
        runners = {str(h.get("n")) for h in race.get("ranked_snapshot", [])}
        row = {"date": key[0], "track": key[1], "race_no": key[2], "types": {}}
        for kind, path in PATHS.items():
            item = {"status": "NO_QUOTE", "odds": {}}
            url = "https://sports.yahoo.co.jp/keiba/race/odds/" + path + "/" + code
            try:
                odds = extract(fetch(url), kind, runners)
                if odds:
                    # Parser has not been independently validated against live page samples.
                    item = {"status": "LAYOUT_UNVERIFIED", "odds": odds,
                            "source_url": url, "retrieved_at": now}
                else:
                    item["reason"] = "NO_STRICT_MATCH"
            except Exception as exc:
                item["reason"] = type(exc).__name__
            row["types"][kind] = item
        rows.append(row)
    result = {"mode": "RESEARCH_ONLY", "retrieved_at": now,
              "production_modified": False, "races": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"races": len(rows), "validated_quotes": 0,
                      "note": "external layout requires verification"}))

if __name__ == "__main__":
    main()
