-- Raw articles loaded from the S3 news lake (see news-ingester preprocessing)
create table if not exists news_articles
(
    id           text primary key,
    source       text,
    title        text,
    content      text,
    url          text,
    published_at timestamp with time zone,
    image_url    text,
    category     text,
    symbol       text,
    ingested_at  timestamp with time zone,
    raw_payload  jsonb
);

create index if not exists idx_news_articles_symbol_published
    on news_articles (symbol, published_at);

-- Chunk text written by news-processing; vectors live in Qdrant keyed by id
create table if not exists article_chunks
(
    id          bigserial primary key,
    article_id  text    not null references news_articles,
    chunk_index integer not null,
    content     text    not null,
    token_count integer,
    created_at  timestamp with time zone default now() not null
);
