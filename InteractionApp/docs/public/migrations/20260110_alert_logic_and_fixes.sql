-- Migration: add AND/OR logic to alerts + fix triggeralert constraints
-- Applies to PostgreSQL 13 (interactdb)
--
-- Run with:
--   psql -h localhost -U postgres -d interactdb -f InteractionApp/docs/public/migrations/20260110_alert_logic_and_fixes.sql
--
-- All statements are idempotent so the file can be re-run safely.

begin;

-- 1) alert.logic : single shared boolean operator for all triggers of the alert
alter table alert
    add column if not exists logic varchar(3) not null default 'AND';

alter table alert
    drop constraint if exists alert_logic_check;

alter table alert
    add constraint alert_logic_check check (logic in ('AND', 'OR'));

-- Backfill any pre-existing rows that somehow ended up null.
update alert set logic = 'AND' where logic is null;

-- 2) triggeralert.condition : widen from varchar(1) so ">=", "<=", "==", "!=" fit
alter table triggeralert
    alter column condition type varchar(4);

-- 3) triggeralert.position : stable display ordering of conditions
alter table triggeralert
    add column if not exists position int not null default 0;

-- Backfill a deterministic order for existing rows (per alert, by insertion id).
with ordered as (
    select id,
           row_number() over (partition by alert_id order by id) - 1 as pos
    from triggeralert
)
update triggeralert t
set position = o.pos
from ordered o
where t.id = o.id
  and t.position = 0;

-- 4) Cascade delete so removing an alert also removes its triggers
alter table triggeralert
    drop constraint if exists trigger_alert_fk;

alter table triggeralert
    add constraint trigger_alert_fk
        foreign key (alert_id) references alert (id) on delete cascade;

commit;
