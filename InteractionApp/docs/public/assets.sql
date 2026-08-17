create table assets
(
    id            bigint generated always as identity
        primary key,
    user_id       varchar(100)   not null
        constraint asset_user_fk
            references user_table,
    symbol        varchar(9)     not null
        constraint assets_symbol_fk
            references company_profile,
    quantity      integer        not null,
    average_price numeric(10, 2) not null
);

alter table assets
    owner to postgres;

