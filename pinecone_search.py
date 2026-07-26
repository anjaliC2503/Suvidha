"""Pinecone-backed tool for retrieving scheme source passages."""

import os
from functools import lru_cache
from pathlib import Path

INDEX_NAME = "suvidha-scheme-trial"
NAMESPACE = "trial"
RESULT_FIELDS = ("chunk_text", "slug", "title", "section", "state", "source_url")

TOOL_DEFINITION = {
    "type": "function",
    "name": "search_pinecone_schemes",
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
            "top_k": {
                "type": "integer",
                "minimum": 1,
                "maximum": 5,
                "description": "Number of passages to return. Defaults to 3.",
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


@lru_cache(maxsize=1)
def pinecone_index():
    load_dotenv()
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY must be set in .env or the environment")

    from pinecone import Pinecone

    return Pinecone(api_key=api_key).Index(os.environ.get("PINECONE_INDEX", INDEX_NAME))


def search_pinecone_schemes(query, top_k=3):
    """Return grounded scheme passages for one agent tool invocation."""
    if not isinstance(query, str) or not (query := query.strip()):
        raise ValueError("query must be a non-empty string")
    if len(query) > 2_000:
        raise ValueError("query must not exceed 2,000 characters")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 5:
        raise ValueError("top_k must be an integer from 1 through 5")

    result = pinecone_index().search(
        namespace=os.environ.get("PINECONE_NAMESPACE", NAMESPACE),
        top_k=top_k,
        inputs={"text": query},
        fields=RESULT_FIELDS,
    )
    hits = result.to_dict()["result"]["hits"]
    return [
        {**hit["fields"], "score": hit["score"]}
        for hit in hits
    ]
