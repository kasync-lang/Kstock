create table company_profile
(
    ticker                varchar(9) not null
        primary key,
    name                  text,
    country               varchar(20),
    currency              varchar(10),
    exchange              varchar(50),
    ipo                   date,
    market_capitalization double precision,
    share_outstanding     double precision,
    phone                 varchar(20),
    weburl                text,
    logo                  text,
    finnhub_industry      varchar(100)
);

alter table company_profile
    owner to postgres;

-- Indexes for /api/symbols performance optimization
CREATE INDEX IF NOT EXISTS idx_company_profile_exchange_name ON company_profile (exchange, name);
CREATE INDEX IF NOT EXISTS idx_company_profile_ticker_pattern ON company_profile (ticker varchar_pattern_ops);
CREATE INDEX IF NOT EXISTS idx_company_profile_name_pattern ON company_profile (name text_pattern_ops);
CREATE INDEX IF NOT EXISTS idx_company_profile_market_cap ON company_profile (market_capitalization DESC NULLS LAST);


