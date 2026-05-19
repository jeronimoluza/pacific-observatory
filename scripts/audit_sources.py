"""Probe each source's homepage and classify what the site actually is.
Flags possible non-news sources: SEO farms, advice portals, Q&A sites, blogs,
gov press release dumps, aggregators.
"""
import os, sys, re, argparse
import glob
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import yaml
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Keywords that suggest non-news content
FINANCE_ADVICE = {"loan", "credit", "savings", "investment", "forex", "earn money",
                  "pul", "kredit", "investisiya"}  # uz/ru finance terms
SEO_SIGNALS = {"how to", "best of", "top 10", "5 ways", "qanday", "как ",
               "10 лучших", "качай", "скачать бесплатно"}
GOV_SIGNALS = {"press release", "ministry of", "official portal", "gov.",
               "прес-реліз", "офіційний", "пресс-релиз"}

def probe(yaml_path: str) -> dict:
    try:
        with open(yaml_path) as f:
            cfg = yaml.safe_load(f)
    except Exception as e:
        return {"path": yaml_path, "error": f"yaml: {e}"}
    name = cfg.get("name", "?")
    base = cfg.get("base_url", "").rstrip("/")
    lang = cfg.get("language", "?")
    country = cfg.get("country", "?")
    parts = yaml_path.split("/")
    source_key = parts[-1][:-5]

    out = {"path": yaml_path, "source": source_key, "name": name, "lang": lang,
           "country": country, "base": base}
    if not base:
        out["flag"] = "no_base_url"
        return out

    try:
        r = httpx.get(base, headers=HEADERS, timeout=15, follow_redirects=True)
    except Exception as e:
        out["flag"] = f"fetch_error: {type(e).__name__}"
        return out
    if r.status_code != 200:
        out["flag"] = f"http_{r.status_code}"
        return out

    soup = BeautifulSoup(r.text, "html.parser")
    title_tag = soup.find("title")
    out["title"] = (title_tag.get_text(strip=True)[:120] if title_tag else "")
    desc = soup.find("meta", attrs={"name": "description"})
    out["desc"] = (desc.get("content", "")[:200] if desc else "")
    og_site = soup.find("meta", attrs={"property": "og:site_name"})
    out["site_name"] = og_site.get("content", "") if og_site else ""

    # Extract top headlines
    headlines = []
    for h in soup.find_all(["h1", "h2", "h3"])[:20]:
        t = h.get_text(strip=True)
        if 10 < len(t) < 200:
            headlines.append(t)
    out["sample_headlines"] = headlines[:10]

    # Categorize by URL patterns in nav
    nav_paths = set()
    for a in soup.find_all("a", href=True)[:100]:
        h = a["href"]
        if base in h:
            p = h.replace(base, "").strip("/").split("/")
            if p and p[0] and len(p[0]) < 30 and not p[0].startswith("#"):
                nav_paths.add(p[0])
    out["nav_sections"] = sorted(nav_paths)[:15]

    # Heuristic flags
    text_blob = (out["title"] + " " + out["desc"] + " " + " ".join(headlines)).lower()
    flags = []
    if any(k in text_blob for k in FINANCE_ADVICE):
        flags.append("finance_advice")
    qa_pattern = sum(1 for h in headlines if h.rstrip("?").endswith(("?", "?", "?")) or
                     h.startswith(("How", "What", "Why", "Qanday", "Как ", "Почему", "Что ")))
    if qa_pattern >= 3:
        flags.append(f"Q&A_{qa_pattern}")
    if any(k in text_blob for k in SEO_SIGNALS):
        flags.append("seo_signals")
    if any(k in text_blob for k in GOV_SIGNALS) or "gov" in base:
        flags.append("gov")
    if "blog" in base or "blog" in (out["site_name"] or "").lower():
        flags.append("blog")
    # Corpus size: tiny nav sections = likely narrow topic
    if len(nav_paths) < 4 and headlines:
        flags.append(f"few_nav_{len(nav_paths)}")

    out["flags"] = flags
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default="src/text/configs/eca/central_asia/*/*.yaml")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--output", default="/tmp/audit_ca.json")
    args = ap.parse_args()

    files = [p for p in glob.glob(args.glob) if not os.path.basename(p).startswith("_")]
    print(f"Auditing {len(files)} configs...", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(probe, p): p for p in files}
        for i, fut in enumerate(as_completed(futures), 1):
            results.append(fut.result())
            if i % 10 == 0:
                print(f"  {i}/{len(files)}", flush=True)

    # Save full
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {args.output}")

    # Print flagged ones
    flagged = [r for r in results if r.get("flags") or r.get("error") or r.get("flag")]
    print(f"\n=== FLAGGED ({len(flagged)} / {len(results)}) ===\n")
    for r in sorted(flagged, key=lambda x: (x.get("country",""), x.get("source",""))):
        src = f"{r.get('country','?')}/{r.get('source','?')}"
        flags = r.get("flags", []) or [r.get("flag", r.get("error", "?"))]
        print(f"  [{', '.join(flags)}]  {src}")
        print(f"    name: {r.get('name','?')}")
        if r.get("title"): print(f"    title: {r['title'][:90]}")
        if r.get("desc"): print(f"    desc:  {r['desc'][:90]}")
        if r.get("nav_sections"): print(f"    nav:   {r['nav_sections'][:10]}")
        print()


if __name__ == "__main__":
    main()
