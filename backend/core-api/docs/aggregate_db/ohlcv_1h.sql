create table ohlcv_1h
(
    symbol    LowCardinality(String),
    timestamp DateTime,
    open      Float64,
    high      Float64,
    low       Float64,
    close     Float64,
    volume    Float64
)
    engine = MergeTree PARTITION BY toYYYYMM(timestamp)
        ORDER BY (symbol, timestamp)
        SETTINGS index_granularity = 8192;

