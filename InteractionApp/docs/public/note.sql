create table note
(
    note_id    uuid      default gen_random_uuid() not null
        primary key,
    user_id    varchar(100),
    symbol     varchar(9)
        constraint kf_symbol_note
            references company_profile,
    title      text,
    content    text,
    created_at timestamp default now(),
    updated_at timestamp default now()
);

alter table note
    owner to postgres;

