"""Public HTTP API for the agent's scheme-search tool."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from scheme_search import load_dotenv, search_schemes

load_dotenv()
app = FastAPI(title="Suvidha Scheme Search API", version="1.0.0")


class SchemeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    state: str | None = Field(default=None, max_length=100)
    top_k: int = Field(default=3, ge=1, le=5)


class SchemeSearchResponse(BaseModel):
    results: list[dict]




@app.post("/v1/schemes/search", response_model=SchemeSearchResponse)
def scheme_search(request: SchemeSearchRequest):
    try:
        return {"results": search_schemes(request.query, request.state, request.top_k)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Scheme search is temporarily unavailable") from error
