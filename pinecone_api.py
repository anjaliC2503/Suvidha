"""Public HTTP API for the Pinecone-backed scheme-search tool."""

import hmac
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from pinecone_search import load_dotenv, search_pinecone_schemes

load_dotenv()
app = FastAPI(title="Suvidha Pinecone Scheme Search API", version="1.0.0")


class SchemeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=3, ge=1, le=5)


class SchemeSearchResponse(BaseModel):
    results: list[dict]


def require_tool_key(authorization: str | None = Header(default=None)):
    expected = os.environ.get("SUVIDHA_TOOL_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="Tool authentication is not configured")

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Invalid tool credentials")


@app.post("/v1/pinecone/schemes/search", response_model=SchemeSearchResponse)
def pinecone_scheme_search(
    request: SchemeSearchRequest,
    authorization: str | None = Header(default=None),
):
    require_tool_key(authorization)
    try:
        return {"results": search_pinecone_schemes(request.query, request.top_k)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Pinecone scheme search is temporarily unavailable") from error
