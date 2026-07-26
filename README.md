# Suvidha

## Supabase pgvector scheme search

`supabase_schemes.py` embeds `chunk_text` with OpenAI's `text-embedding-3-small` and stores the 1,536-dimension vectors in Supabase pgvector. It splits each scraped Markdown scheme by section, excludes `## Complete Source Data`, and stores the source chunk plus `slug`, `title`, `section`, `state`, and `source_url`.

Create a Supabase project, then run `supabase_schema.sql` once in its SQL Editor. Configure `OPENAI_API_KEY`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY` in `.env`.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python supabase_schemes.py
```

The default command clears `scheme_chunks`, loads three representative schemes, and verifies three semantic retrievals. After scraping completes, replace the corpus:

```sh
.venv/bin/python supabase_schemes.py --all
```

To add or refresh records without clearing the table:

```sh
.venv/bin/python supabase_schemes.py --all --append
```

For the app, query with a profile sentence assembled from already-collected facts. `search_schemes()` gets several pgvector cosine matches, then returns each scheme's best chunk. It narrows candidates only; deterministic eligibility rules decide eligibility.

### Agent tool

`scheme_search.py` exports `TOOL_DEFINITION` and `search_schemes()`. Register the definition with the model's function-calling API. When the model calls `search_schemes`, pass its JSON arguments to the function and return the JSON result to the model. Keep this code server-side: OpenAI and Supabase service-role keys must never reach the browser.

```python
import json

from scheme_search import TOOL_DEFINITION, search_schemes

response = client.responses.create(
    model="gpt-4.1-mini",
    input=user_message,
    tools=[TOOL_DEFINITION],
)

tool_outputs = [
    {
        "type": "function_call_output",
        "call_id": call.call_id,
        "output": json.dumps(search_schemes(**json.loads(call.arguments))),
    }
    for call in response.output
    if call.type == "function_call" and call.name == "search_schemes"
]
if tool_outputs:
    response = client.responses.create(
        model="gpt-4.1-mini",
        previous_response_id=response.id,
        input=tool_outputs,
    )
```

The agent instruction should require a search before discussing a specific scheme and state that tool output is source material, never executable instructions. For Anthropic, register the same name, description, and `TOOL_DEFINITION["parameters"]` as the tool's `input_schema`; dispatch `tool_use.input` to `search_schemes(**tool_use.input)`.

## Separate Pinecone endpoint

`pinecone_api.py` is independent of the Supabase route. It queries the Pinecone integrated-embedding index and exposes `POST /v1/pinecone/schemes/search`.

Set `PINECONE_API_KEY` and, if needed, `PINECONE_INDEX` and `PINECONE_NAMESPACE`. Start it with:

```sh
.venv/bin/uvicorn pinecone_api:app
```

Send a bearer token matching `SUVIDHA_TOOL_API_KEY`:

```sh
curl http://127.0.0.1:8000/v1/pinecone/schemes/search \
  -H "Authorization: Bearer $SUVIDHA_TOOL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"Rajasthan farmer needs crop support","top_k":3}'
```

For direct model function calling, `pinecone_search.py` exports `TOOL_DEFINITION` and `search_pinecone_schemes()`.