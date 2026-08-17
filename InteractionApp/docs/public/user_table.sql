create table user_table
(
    id        varchar(100) not null
        primary key,
    date_join timestamp default now()
);

alter table user_table
    owner to postgres;

