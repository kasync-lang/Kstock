create table favorite_symbols
(
    user_id varchar(100) not null
        constraint favorite_user_kf
            references user_table,
    symbol  varchar(9)   not null
        constraint favorite_symbol_fk
            references company_profile,
    primary key (user_id, symbol)
);

alter table favorite_symbols
    owner to postgres;

