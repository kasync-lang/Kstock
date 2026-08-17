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

