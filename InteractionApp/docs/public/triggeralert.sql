create table triggeralert
(
    id        uuid default gen_random_uuid() not null
        primary key,
    alert_id  uuid
        constraint trigger_alert_fk
            references alert,
    indicator varchar(50),
    value     double precision,
    condition varchar(1)
);

alter table triggeralert
    owner to postgres;

