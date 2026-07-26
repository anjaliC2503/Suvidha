create extension if not exists vector;

create table if not exists public.scheme_chunks (
    id text primary key,
    chunk_text text not null,
    slug text not null,
    title text not null,
    section text not null,
    state text not null default '',
    source_url text not null default '',
    embedding vector(1536) not null
);

create index if not exists scheme_chunks_embedding_idx
    on public.scheme_chunks using hnsw (embedding vector_cosine_ops);

alter table public.scheme_chunks enable row level security;

create or replace function public.match_scheme_chunks(
    query_embedding vector(1536),
    match_count integer,
    requested_state text default null
)
returns table (
    id text,
    score real,
    chunk_text text,
    slug text,
    title text,
    section text,
    state text,
    source_url text
)
language sql
stable
set search_path = public
as $$
    with nearest_chunks as (
        select
            scheme_chunks.*,
            scheme_chunks.embedding <=> query_embedding as distance
        from public.scheme_chunks
        order by scheme_chunks.embedding <=> query_embedding
        limit greatest(match_count * 4, 40)
    )
    select
        id,
        (1 - distance)::real as score,
        chunk_text,
        slug,
        title,
        section,
        state,
        source_url
    from nearest_chunks
    where requested_state is null
       or state = ''
       or state = requested_state
    order by distance
    limit match_count;
$$;
