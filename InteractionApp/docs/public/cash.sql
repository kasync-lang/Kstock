CREATE TABLE IF NOT EXISTS public.cash
(
    user_id varchar(100) NOT NULL
        PRIMARY KEY
        REFERENCES public.user_table(id),
    amount numeric(12, 2) NOT NULL DEFAULT 0
        CHECK (amount >= 0)
);

ALTER TABLE public.cash
    owner to postgres;

-- One-time, idempotent migration for installations where USD was represented
-- by an assets row. Execute this after creating cash and before removing USD.
INSERT INTO public.cash (user_id, amount)
SELECT user_id, quantity
FROM public.assets
WHERE symbol = 'USD'
ON CONFLICT (user_id) DO UPDATE
SET amount = EXCLUDED.amount;

-- USD is no longer a portfolio asset; all future balance changes use cash.
DELETE FROM public.assets
WHERE symbol = 'USD';

