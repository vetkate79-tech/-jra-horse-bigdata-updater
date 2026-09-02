#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import Request, urlopen

from lxml import html

OUT = Path("docs/data/jra-official-terms.json")
UA = "Mozilla/5.0 (compatible; JRA-AI-Glossary/1.0; +https://github.com/vetkate79-tech/-jra-horse-bigdata-updater)"
DOMESTIC_CODES = "a i u e o ka ki ku ke ko sa si su se so ta ti tu te to na ni nu ne no ha hi hu he ho ma mi mu me mo ya yu yo ra ri ru re ro wa".split()
UNIT_XPATH = '//div[contains(concat(" ",normalize-space(@class)," ")," detail_unit ")]'


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def fetch(url: str, attempts: int = 3) -> bytes:
    last = None
    for attempt in range(attempts):
        try:
            req = Request(url, headers={"User-Agent": UA, "Accept-Language": "ja-JP,ja;q=0.9"})
            with urlopen(req, timeout=45) as response:
                return response.read()
        except Exception as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"JRA glossary fetch failed: {url}: {last}")


def text_at(unit, xpath: str) -> str:
    nodes = unit.xpath(xpath)
    return clean(nodes[0].text_content()) if nodes else ""


def categories_at(unit: object, fallback: str) -> list[str]:
    nodes = unit.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," category ")]')
    if not nodes:
        return [fallback]
    values = [clean(x.text_content()) for x in nodes[0].xpath('.//a')]
    values = [x for x in values if x]
    return list(dict.fromkeys(values)) or [fallback]


def parse_page(code: str) -> list[dict]:
    url = f"https://www.jra.go.jp/kouza/yougo/{code}_list.html"
    fallback = "その他"
    page = html.fromstring(fetch(url).decode("shift_jis", "replace"))
    terms = []
    for unit in page.xpath(UNIT_XPATH):
        term = text_at(unit, ".//h3")
        if not term:
            continue
        reading = text_at(unit, './/div[contains(concat(" ",normalize-space(@class)," ")," yomi ")]')
        reading = re.sub(r"^読み\s*", "", reading)
        categories = categories_at(unit, fallback)
        category_label = " / ".join(categories)
        summary = f"JRA公式競馬用語辞典に掲載されている「{category_label}」分野の用語。詳しい意味はJRA公式の出典ページで確認できます。"
        source_name = "JRA公式 競馬用語辞典"
        terms.append({
            "term": term,
            "reading": reading,
            "category": categories[0],
            "categories": categories,
            "summary": summary,
            "aliases": [],
            "source_name": source_name,
            "source_url": url,
            "source_authority": "JRA",
            "source_kind": "domestic",
        })
    return terms


def key(term: str) -> str:
    return re.sub(r"[\s・･._\-ー()（）]", "", term).casefold()


def main() -> None:
    jobs = DOMESTIC_CODES
    collected = []
    failures = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(parse_page, code): code for code in jobs}
        for future in as_completed(futures):
            code = futures[future]
            try:
                collected.extend(future.result())
            except Exception as exc:
                failures.append({"kind": "domestic", "code": code, "error": str(exc)})
    if failures:
        raise RuntimeError(json.dumps({"failures": failures}, ensure_ascii=False))
    unique = {}
    for item in collected:
        unique.setdefault(key(item["term"]), item)
    terms = sorted(unique.values(), key=lambda item: item["term"].casefold())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema_version": 2,
        "authority": "Japan Racing Association",
        "policy": "Terms, readings and classifications are indexed as factual metadata. Explanations on this site are original summaries and do not reproduce JRA definition text.",
        "source_urls": ["https://www.jra.go.jp/kouza/yougo/"],
        "count": len(terms),
        "terms": terms,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "count": len(terms),
        "domestic": len(terms),
        "output": str(OUT),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
