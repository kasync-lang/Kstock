create table alert
(
    user_id    varchar(100)
        constraint alert_user_fk
            references user_table,
    symbol     varchar(9)
        constraint alert_symbol_fk
            references company_profile,
    status     boolean,
    logic      varchar(3) default 'AND' not null
        constraint alert_logic_check
            check (logic in ('AND', 'OR')),
    created_at timestamp default now(),
    updated_at timestamp default now(),
    id         uuid      default gen_random_uuid() not null
        primary key
);

alter table alert
    owner to postgres;

