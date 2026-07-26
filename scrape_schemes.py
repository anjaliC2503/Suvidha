#!/usr/bin/env python3
import argparse
import concurrent.futures
import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API_ROOT = "https://api.myscheme.gov.in"
API_KEY = "tYTy5eEhlu9rFjyxuCr7ra7ACp4dv1RH8gWuHTDc"
HEADERS = {
    "x-api-key": API_KEY,
    "Origin": "https://www.myscheme.gov.in",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
}
OUTPUT_DIR = Path(__file__).with_name("schemedata")

REQUEST_INTERVAL = 0.25
request_lock = threading.Lock()
next_request_at = 0.0


def throttle():
    global next_request_at
    with request_lock:
        now = time.monotonic()
        time.sleep(max(0, next_request_at - now))
        next_request_at = time.monotonic() + REQUEST_INTERVAL


def get_json(url, optional=False):
    for attempt in range(8):
        try:
            throttle()
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.load(response)
            if payload.get("statusCode") != 200:
                if optional:
                    return payload
                raise RuntimeError(payload.get("errorDescription") or payload)
            return payload
        except urllib.error.HTTPError as error:
            if error.code == 429:
                wait = int(error.headers.get("Retry-After", 60)) * (attempt + 1)
                print(f"Rate limited; waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            if optional and error.code in {404, 412}:
                return {"status": "Unavailable", "error": str(error), "data": None}
            if attempt == 7:
                raise
            time.sleep(2**attempt)
        except Exception:
            if attempt == 7:
                raise
            time.sleep(2**attempt)


def discover_schemes(limit=None):
    schemes = []
    offset = 0
    while True:
        query = urllib.parse.urlencode({
            "lang": "en",
            "q": "[]",
            "keyword": "",
            "sort": "schemename-asc",
            "from": offset,
            "size": 100,
        })
        payload = get_json(f"{API_ROOT}/search/v6/schemes?{query}")
        hits = payload["data"]["hits"]
        schemes.extend(item["fields"] for item in hits["items"])
        target = min(hits["page"]["total"], limit) if limit else hits["page"]["total"]
        print(f"Discovered {min(len(schemes), target)}/{target}", flush=True)
        if len(schemes) >= target or not hits["items"]:
            return schemes[:target]
        offset += 100


def rich_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (rich_text(item) for item in value)))
    if not isinstance(value, dict):
        return "" if value is None else str(value)
    text = value.get("text", "")
    if value.get("bold") and text:
        text = f"**{text}**"
    if value.get("link"):
        text = f"[{text or value['link']}]({value['link']})"
    children = rich_text(value.get("children", []))
    combined = text + children
    if value.get("type") == "list_item":
        return f"- {combined}"
    return combined


def display_value(value):
    if isinstance(value, dict) and "label" in value:
        return str(value["label"])
    if isinstance(value, list):
        return ", ".join(display_value(item) for item in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None or value == "":
        return "Not specified"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def clean_markdown(value, fallback=None):
    text = value or rich_text(fallback)
    return html.unescape(text).strip() if text else ""


def render_markdown(summary, detail_payload, documents_payload, faqs_payload, channels_payload):
    detail = detail_payload.get("data") or {
        "slug": summary["slug"],
        "en": {
            "basicDetails": summary,
            "schemeContent": {"briefDescription": summary.get("briefDescription", "")},
        },
    }
    language = detail.get("en", {})
    basic = language.get("basicDetails", {})
    content = language.get("schemeContent", {})
    eligibility = language.get("eligibilityCriteria", {})
    name = basic.get("schemeName") or summary.get("schemeName") or detail["slug"]
    slug = detail["slug"]

    lines = [
        f"# {name}",
        "",
        f"- **Slug:** `{slug}`",
        f"- **Scheme ID:** `{detail.get('_id', '')}`",
        f"- **myScheme page:** https://www.myscheme.gov.in/schemes/{slug}",
    ]

    for key, value in basic.items():
        label = re.sub(r"(?<!^)(?=[A-Z])", " ", key).replace("_", " ").title()
        lines.append(f"- **{label}:** {display_value(value)}")

    sections = [
        ("Brief Description", clean_markdown(content.get("briefDescription"))),
        ("Detailed Description", clean_markdown(content.get("detailedDescription_md"), content.get("detailedDescription"))),
        ("Benefits", clean_markdown(content.get("benefits_md"), content.get("benefits"))),
        ("Exclusions", clean_markdown(content.get("exclusions_md"), content.get("exclusions"))),
        ("Eligibility", clean_markdown(eligibility.get("eligibilityDescription_md"), eligibility.get("eligibilityDescription"))),
    ]
    for title, body in sections:
        if body and body not in {"<br>", "<br/>"}:
            lines.extend(["", f"## {title}", "", body])

    applications = language.get("applicationProcess") or []
    if applications:
        lines.extend(["", "## Application Process"])
        for application in applications:
            mode = application.get("mode", "Application")
            lines.extend(["", f"### {mode}"])
            if application.get("url"):
                lines.extend(["", f"**Application URL:** {application['url'].strip()}"])
            process = clean_markdown(application.get("process_md"), application.get("process"))
            if process:
                lines.extend(["", process])

    definitions = language.get("schemeDefinitions") or []
    if definitions:
        lines.extend(["", "## Definitions", "", rich_text(definitions)])

    references = content.get("references") or []
    if references:
        lines.extend(["", "## References", ""])
        for reference in references:
            title = reference.get("title") or reference.get("url")
            url = (reference.get("url") or "").strip()
            lines.append(f"- [{title}]({url})" if url else f"- {title}")

    documents = ((documents_payload.get("data") or {}).get("en") or {})
    documents_md = clean_markdown(documents.get("documentsRequired_md"), documents.get("documents_required"))
    if documents_md:
        lines.extend(["", "## Documents Required", "", documents_md])

    faqs = (((faqs_payload.get("data") or {}).get("en") or {}).get("faqs") or [])
    if faqs:
        lines.extend(["", "## Frequently Asked Questions"])
        for faq in faqs:
            answer = clean_markdown(faq.get("answer_md"), faq.get("answer"))
            lines.extend(["", f"### {faq.get('question', 'Question').strip()}", "", answer or "Not specified."])

    channels = channels_payload.get("data")
    if channels:
        lines.extend([
            "",
            "## Application Channels",
            "",
            "````json",
            json.dumps(channels, ensure_ascii=False, indent=2),
            "````",
        ])

    lines.extend([
        "",
        "## Complete Source Data",
        "",
        "The following preserves every field returned by the public-facing APIs.",
        "",
        "````json",
        json.dumps({
            "searchSummary": summary,
            "scheme": detail_payload,
            "documents": documents_payload,
            "faqs": faqs_payload,
            "applicationChannels": channels_payload,
        }, ensure_ascii=False, indent=2),
        "````",
        "",
    ])
    return "\n".join(lines)


def export_scheme(summary, refresh=False):
    slug = summary["slug"]
    filename = re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-") + ".md"
    destination = OUTPUT_DIR / filename
    if destination.exists() and destination.stat().st_size and not refresh:
        return slug, "skipped"

    encoded_slug = urllib.parse.quote(slug, safe="")
    detail = get_json(f"{API_ROOT}/schemes/v6/public/schemes?slug={encoded_slug}&lang=en")
    if detail.get("data"):
        scheme_id = detail["data"]["_id"]
        base = f"{API_ROOT}/schemes/v6/public/schemes/{scheme_id}"
        documents = get_json(f"{base}/documents?lang=en", optional=True)
        faqs = get_json(f"{base}/faqs?lang=en", optional=True)
        channels = get_json(f"{base}/applicationchannel", optional=True)
    else:
        documents = faqs = channels = {"status": "Unavailable", "data": None}
    markdown = render_markdown(summary, detail, documents, faqs, channels)

    temporary = destination.with_suffix(".md.tmp")
    temporary.write_text(markdown, encoding="utf-8")
    os.replace(temporary, destination)
    return slug, "written"


def main():
    parser = argparse.ArgumentParser(description="Export myScheme records to Markdown")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    schemes = discover_schemes(args.limit)
    failures = []
    completed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(export_scheme, scheme, args.refresh): scheme for scheme in schemes}
        for future in concurrent.futures.as_completed(futures):
            scheme = futures[future]
            try:
                slug, status = future.result()
                completed += 1
                print(f"[{completed}/{len(schemes)}] {status}: {slug}", flush=True)
            except Exception as error:
                failures.append((scheme["slug"], str(error)))
                print(f"FAILED: {scheme['slug']}: {error}", flush=True)

    if failures:
        print("\nFailures:")
        for slug, error in failures:
            print(f"- {slug}: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
