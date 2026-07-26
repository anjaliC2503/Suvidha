#!/usr/bin/env python3
"""Supabase pgvector-backed tool for retrieving scheme source passages."""

import argparse
import json
import os
from pathlib import Path

from supabase_schemes import require_environment, search_records

TOOL_DEFINITION = {
    "type": "function",
    "name": "search_schemes",
    "description": (
        "Find government-scheme source passages relevant to a person's need. "
        "Use this before discussing benefits, documents, application steps, or eligibility. "
        "It retrieves candidates only; do not claim someone is eligible without checking the returned criteria."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The person's need and known facts, such as occupation, state, age, income, or dependants.",
            },
            "state": {
                "type": "string",
                "description": "Known Indian state or union territory. Omit when unknown.",
            },
            "top_k": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "Number of distinct schemes to return. Defaults to 3.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}


def load_dotenv(path=Path(".env")):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key and not key.startswith("#"):
            os.environ.setdefault(key, value)


def search_schemes(query, state=None, top_k=3):
    """Return grounded scheme passages for one agent tool invocation."""
    if not isinstance(query, str) or not (query := query.strip()):
        raise ValueError("query must be a non-empty string")
    if len(query) > 2_000:
        raise ValueError("query must not exceed 2,000 characters")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 5:
        raise ValueError("top_k must be an integer from 1 through 5")
    if state is not None and (not isinstance(state, str) or len(state.strip()) > 100):
        raise ValueError("state must be a string up to 100 characters")

    require_environment()
    schemes = []
    seen_slugs = set()
    for hit in search_records(query, state, top_k):
        if hit["slug"] in seen_slugs:
            continue
        seen_slugs.add(hit["slug"])
        schemes.append(hit)
        if len(schemes) == top_k:
            break
    return schemes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--state")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(search_schemes(args.query, args.state, args.top_k), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
