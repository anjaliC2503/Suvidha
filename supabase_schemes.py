#!/usr/bin/env python3
"""Load scraped schemes with OpenAI embeddings into Supabase pgvector."""

import argparse
import concurrent.futures
import json
import os
import re
import urllib.error
import time
import urllib.parse
import urllib.request
from pathlib import Path

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
MAX_CHARS = 6_000
EMBEDDING_BATCH_SIZE = 100
UPSERT_BATCH_SIZE = 50
DEFAULT_SCHEMES = (
    "schemedata/fp.md",
    "schemedata/haryana-building-and-other-construction-workers-welfare-board.md",
    "schemedata/aiideals.md",
)
DEFAULT_CHECKS = {
    "Rajasthan farmer wants support to demonstrate new crop techniques": "fp",
    "Haryana construction worker died and their spouse needs pension": "haryana-building-and-other-construction-workers-welfare-board",
    "funding for an AICTE engineering innovation lab": "aiideals",
}


def load_dotenv(path=Path(".env")):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key and not key.startswith("#"):
            os.environ.setdefault(key, value)


def require_environment():
    load_dotenv()
    required = ("OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")


def request_json(url, method="GET", payload=None, headers=None):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
        method=method,
    )
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
            return json.loads(body) if body else None
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            if error.code in (429, 500, 502, 503, 504) and attempt < 5:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"{method} {url} failed ({error.code}): {detail}") from error


def openai_embeddings(texts):
    if not texts:
        return []
    response = request_json(
        "https://api.openai.com/v1/embeddings",
        method="POST",
        payload={
            "model": os.environ.get("OPENAI_EMBEDDING_MODEL", EMBEDDING_MODEL),
            "input": texts,
            "dimensions": EMBEDDING_DIMENSIONS,
            "encoding_format": "float",
        },
        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
    )
    return [item["embedding"] for item in sorted(response["data"], key=lambda item: item["index"])]


def supabase_headers():
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def supabase_url(path):
    return f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1/{path.lstrip('/')}"


def scheme_metadata(markdown):
    header = markdown.split("## Brief Description", 1)[0]

    def field(label):
        match = re.search(rf"^- \*\*{re.escape(label)}:\*\* (.+)$", header, re.MULTILINE)
        return match.group(1).strip() if match else ""

    return {
        "title": re.search(r"^# (.+)$", header, re.MULTILINE).group(1).strip(),
        "slug": field("Slug").strip("`"),
        "state": field("State"),
        "source_url": field("myScheme page"),
    }


def split_section(text):
    parts, chunk = [], ""
    for paragraph in text.split("\n\n"):
        if chunk and len(chunk) + len(paragraph) + 2 > MAX_CHARS:
            parts.append(chunk)
            chunk = ""
        chunk = f"{chunk}\n\n{paragraph}".strip()
    if chunk:
        parts.append(chunk)
    return parts


def records_from_scheme(path):
    markdown = Path(path).read_text(encoding="utf-8")
    metadata = scheme_metadata(markdown)
    body = markdown.split("## Complete Source Data", 1)[0]
    sections = re.split(r"^## (.+)$", body, flags=re.MULTILINE)
    records = []
    for index in range(1, len(sections), 2):
        section, text = sections[index].strip(), sections[index + 1].strip()
        for part, chunk in enumerate(split_section(text)):
            records.append({
                "id": f"{metadata['slug']}:{section.lower().replace(' ', '-')}-{part}",
                "chunk_text": f"Scheme: {metadata['title']}\nState: {metadata['state']}\nSection: {section}\n\n{chunk}",
                "slug": metadata["slug"],
                "title": metadata["title"],
                "section": section,
                "state": metadata["state"],
                "source_url": metadata["source_url"],
            })
    return records


def batches(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def clear_records():
    request_json(
        supabase_url("scheme_chunks?id=not.is.null"),
        method="DELETE",
        headers=supabase_headers(),
    )

def existing_ids():
    existing, offset = set(), 0
    while True:
        page = request_json(
            supabase_url(f"scheme_chunks?select=id&order=id&offset={offset}&limit=1000"),
            headers=supabase_headers(),
        )
        existing.update(record["id"] for record in page)
        if len(page) < 1000:
            return existing
        offset += len(page)


def upload_batch(batch):
    embeddings = openai_embeddings([record["chunk_text"] for record in batch])
    for record, embedding in zip(batch, embeddings, strict=True):
        record["embedding"] = embedding
    for upsert_batch in batches(batch, UPSERT_BATCH_SIZE):
        request_json(
            supabase_url("scheme_chunks?on_conflict=id"),
            method="POST",
            payload=upsert_batch,
            headers={**supabase_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
        )
    return len(batch)




def upsert_records(records, workers=1):
    batch_list = list(batches(records, EMBEDDING_BATCH_SIZE))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(upload_batch, batch) for batch in batch_list]
        uploaded = 0
        for batch_number, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            uploaded += future.result()
            if batch_number % 10 == 0 or uploaded == len(records):
                print(f"Uploaded {uploaded}/{len(records)} chunks", flush=True)


def search_records(query, state=None, top_k=3):
    embedding = openai_embeddings([query])[0]
    return request_json(
        supabase_url("rpc/match_scheme_chunks"),
        method="POST",
        payload={
            "query_embedding": embedding,
            "match_count": top_k * 4,
            "requested_state": state.strip() if state and state.strip() else None,
        },
        headers=supabase_headers(),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scheme", action="append", default=[])
    parser.add_argument("--all", action="store_true", help="Index every Markdown file in schemedata/")
    parser.add_argument("--append", action="store_true", help="Index only records absent from the table")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    require_environment()
    paths = tuple(sorted(Path("schemedata").glob("*.md"))) if args.all else args.scheme or DEFAULT_SCHEMES
    records = [record for path in paths for record in records_from_scheme(path)]
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    if args.append:
        existing = existing_ids()
        records = [record for record in records if record["id"] not in existing]
    else:
        clear_records()
    upsert_records(records, args.workers)
    print(f"Indexed {len(records)} chunks from {len(paths)} schemes")

    checks = DEFAULT_CHECKS if not args.scheme and not args.all else {}
    failures = []
    for query, expected_slug in checks.items():
        results = search_records(query, top_k=1)
        actual_slug = results[0]["slug"] if results else None
        print(json.dumps({"query": query, "expected": expected_slug, "actual": actual_slug}, ensure_ascii=False))
        if actual_slug != expected_slug:
            failures.append((query, expected_slug, actual_slug))
    if failures:
        raise SystemExit(f"Semantic retrieval checks failed: {failures}")


if __name__ == "__main__":
    main()
