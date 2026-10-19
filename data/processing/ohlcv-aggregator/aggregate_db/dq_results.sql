create table dq_results
(
    run_id     String,
    trade_date Date,
    layer      LowCardinality(String),
    dataset    LowCardinality(String),
    check_name LowCardinality(String),
    symbol     String,
    status     Enum8('pass' = 1, 'warn' = 2, 'fail' = 3),
    observed   Float64,
    threshold  Float64,
    detail     String,
    checked_at DateTime default now()
)
    engine = MergeTree PARTITION BY toYYYYMM(trade_date)
        ORDER BY (trade_date, layer, dataset, check_name, symbol)
        SETTINGS index_granularity = 8192;
