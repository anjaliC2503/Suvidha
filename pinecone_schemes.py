#!/usr/bin/env python3
"""Load representative scraped schemes into a Pinecone integrated-embedding index."""

import argparse
import json
import os
import re
import time
from pathlib import Path

from pinecone import Pinecone
from pinecone.errors.exceptions import NotFoundError

INDEX_NAME = "suvidha-scheme-trial"
NAMESPACE = "trial"
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
MAX_CHARS = 6_000


def load_dotenv(path=Path(".env")):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key and not key.startswith("#"):
            os.environ.setdefault(key, value)


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
                "_id": f"{metadata['slug']}:{section.lower().replace(' ', '-')}-{part}",
                "chunk_text": f"Scheme: {metadata['title']}\nState: {metadata['state']}\nSection: {section}\n\n{chunk}",
                "slug": metadata["slug"],
                "title": metadata["title"],
                "section": section,
                "state": metadata["state"],
                "source_url": metadata["source_url"],
            })
    return records


def wait_until_ready(client, index_name):
    while not client.describe_index(index_name).status["ready"]:
        time.sleep(1)


def index_records(client, index_name, namespace, records):
    if index_name not in client.list_indexes().names():
        client.create_index_for_model(
            name=index_name,
            cloud="aws",
            region="us-east-1",
            embed={"model": "llama-text-embed-v2", "field_map": {"text": "chunk_text"}},
        )
    wait_until_ready(client, index_name)
    index = client.Index(index_name)
    try:
        index.delete(delete_all=True, namespace=namespace)
    except NotFoundError:
        pass
    for start in range(0, len(records), 96):
        index.upsert_records(namespace=namespace, records=records[start:start + 96])
    return index


def result_dict(result):
    return result.to_dict() if hasattr(result, "to_dict") else result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default=INDEX_NAME)
    parser.add_argument("--namespace", default=NAMESPACE)
    parser.add_argument("--scheme", action="append", default=[])
    parser.add_argument("--all", action="store_true", help="Index every Markdown file in schemedata/")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise SystemExit("PINECONE_API_KEY must be set in .env or the environment")

    paths = tuple(sorted(Path("schemedata").glob("*.md"))) if args.all else args.scheme or DEFAULT_SCHEMES
    records = [record for path in paths for record in records_from_scheme(path)]
    index = index_records(Pinecone(api_key=api_key), args.index, args.namespace, records)
    print(f"Indexed {len(records)} chunks from {len(paths)} schemes into {args.index}/{args.namespace}")

    failures = []
    for query, expected_slug in DEFAULT_CHECKS.items():
        result = result_dict(index.search(
            namespace=args.namespace,
            query={"inputs": {"text": query}, "top_k": 1},
            fields=["chunk_text", "slug", "title", "section", "state", "source_url"],
        ))
        hit = result["result"]["hits"][0]
        actual_slug = hit["fields"]["slug"]
        print(json.dumps({"query": query, "expected": expected_slug, "actual": actual_slug, "hit": hit}, ensure_ascii=False))
        if actual_slug != expected_slug:
            failures.append((query, expected_slug, actual_slug))
    if failures:
        raise SystemExit(f"Semantic retrieval checks failed: {failures}")


if __name__ == "__main__":
    main()
