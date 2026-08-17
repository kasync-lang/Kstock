create table transaction
(
    id              uuid      default gen_random_uuid() not null
        primary key,
    amount          numeric                             not null,
    user_id         varchar(100)                        not null
        constraint user_transaction_fk
            references user_table,
    time_transacted timestamp default now()             not null,
    symbol          varchar(9)                          not null
        constraint symbol_transaction_fk
            references company_profile,
    operation       varchar(4)                          not null
        constraint operation_check
            check ((operation)::text = ANY
                   (ARRAY [('BUY'::character varying)::text, ('SELL'::character varying)::text])),
    price           double precision                    not null
);

alter table transaction
    owner to postgres;

