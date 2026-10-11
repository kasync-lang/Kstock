create table triggeralert
(
    id        uuid default gen_random_uuid() not null
        primary key,
    alert_id  uuid
        constraint trigger_alert_fk
            references alert
                on delete cascade,
    indicator varchar(50),
    value     double precision,
    condition varchar(4),
    position  integer default 0 not null
);

alter table triggeralert
    owner to postgres;

