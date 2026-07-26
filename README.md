# Suvidha

## Pinecone scheme trial

The trial uses Pinecone's integrated embedding index: Pinecone embeds `chunk_text` during ingestion and when searching, so no second embedding provider or API key is needed. `pinecone_schemes.py` splits each scraped Markdown scheme by section, excludes `## Complete Source Data`, and stores the source chunk plus filter metadata: `slug`, `title`, `section`, `state`, and `source_url`.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python pinecone_schemes.py
```

The default command creates or reuses `suvidha-scheme-trial`, clears its `trial` namespace, loads three representative schemes, and runs three semantic retrieval assertions. A successful run means the returned top hit matches the expected scheme.

### Backfill after scraping completes

Use a distinct namespace for each corpus version; the command deliberately replaces only the target namespace, making it idempotent and preventing stale chunks for changed schemes.

```sh
.venv/bin/python pinecone_schemes.py --index suvidha-scheme-trial --namespace schemes-20260726 --all
```

For the app, query the same namespace with a profile sentence assembled from already-collected facts (occupation, state, age, income, dependants), request `chunk_text` and the stored fields above, then run the deterministic eligibility rules against the returned candidates. Pinecone narrows the candidate set; it must not decide eligibility.

When serving traffic, backfill a new namespace first, verify it, then switch the application namespace configuration. Do not repopulate the live namespace in place because the script clears it before upserting.