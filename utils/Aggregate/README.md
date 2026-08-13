# Aggregate

Consumes trade ticks from Kafka, builds OHLCV candles, and stores finalized candles in ClickHouse.

## Scope

This service owns only these sub-day intervals: `ohlcv_1m`, `ohlcv_5m`, `ohlcv_15m`, and `ohlcv_1h`.
Daily and weekly aggregation are intentionally not performed here.

## Kafka tick format

```json
{
  "t": 1786388901129,
  "p": 58.28,
  "v": 100,
  "c": ["1", "8"],
  "s": "CTSH"
}
```

`t` is a Unix timestamp in milliseconds. `p`, `v`, and `s` are the price, volume, and symbol. `c` is accepted as optional condition metadata and does not alter OHLCV values.

## Configuration

Set these environment variables; a local `.env` file is loaded automatically:

- `KAFKA_PULL_TOPIC` (default: `ohlcv-topic`)
- `KAFKA_BOOTSTRAP_SERVERS` (default: `localhost:9092`)
- `KAFKA_GROUP_ID` (default: `flink-consumer`)
- `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DB`
- `FLUSH_INTERVAL_SECONDS` (default: `5`)
- `KAFKA_POLL_TIMEOUT_SECONDS` (default: `1.0`)

Create the ClickHouse tables with the SQL files in `aggregate_db/` before starting the service.

## Run

```zsh
uv run python -m src.main
```

## Test

```zsh
uv run python -m unittest discover -s tests -v
```
# Aggregate

Consumes trade ticks from Kafka, builds OHLCV candles, and stores finalized candles in ClickHouse.

## Scope

This service owns only these sub-day intervals:

- `ohlcv_1m`
- `ohlcv_5m`
- `ohlcv_15m`
- `ohlcv_1h`

Daily and weekly aggregation are intentionally not performed here.

## Kafka tick format

```json
{
  "t": 1786388901129,
  "p": 58.28,
  "v": 100,
  "c": ["1", "8"],
  "s": "CTSH"
}
```

`t` is a Unix timestamp in milliseconds; `p`, `v`, and `s` are price, volume, and symbol. `c` is accepted as optional condition metadata and does not alter OHLCV values.

## Configuration

Set these environment variables (a local `.env` file is loaded automatically):

- `KAFKA_PULL_TOPIC` (default: `ohlcv-topic`)
- `KAFKA_BOOTSTRAP_SERVERS` (default: `localhost:9092`)
- `KAFKA_GROUP_ID` (default: `flink-consumer`)
- `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DB`
- `FLUSH_INTERVAL_SECONDS` (default: `5`)
- `KAFKA_POLL_TIMEOUT_SECONDS` (default: `1.0`)

Create the ClickHouse tables with the SQL files in `aggregate_db/` before starting the service.

## Run

```zsh
uv run python -m src.main
```

## Test

```zsh
uv run python -m unittest discover -s tests -v
```

