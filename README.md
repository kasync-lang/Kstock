# Kstock

Mono-repo cho hệ thống **stream giá chứng khoán theo thời gian thực** theo mô hình **event-driven** (Kafka → consumers → WebSocket/API).

---

## Technology Stack

### Backend services

| Service | Language | Framework | Purpose |
|---------|----------|-----------|---------|
| **AuthenApp** | Python 3.10+ | FastAPI | Authentication, JWT/JWK, user management |
| **InteractionApp** | Go 1.25 | Gin | REST API, user interactions (favorites/notes/alerts) |
| **StreamStock** | Go 1.25 | Built-in HTTP + Gorilla WebSocket | Real-time WebSocket server |

### Databases & message queues

- **MongoDB** (async) – user storage (Beanie ORM + Motor async driver) cho AuthenApp
- **PostgreSQL 13** – relational storage (notes, favorites, alerts, assets) cho InteractionApp
- **Apache Kafka** – event streaming layer (tick distribution across consumers)

### Core libraries & patterns

**AuthenApp (Python/FastAPI)**
- `FastAPI` – async REST framework
- `Pydantic` + `pydantic-settings` – config & validation
- `Beanie` – MongoDB async ODM
- `Motor` – async MongoDB client
- `PyJWT` + RSA – JWT generation (private/public key pair)
- `python-jose` – JWT encoding/decoding
- `bcrypt` – password hashing
- `Jinja2` – template rendering

**InteractionApp (Go/Gin)**
- `github.com/gin-gonic/gin` – HTTP routing & middleware
- `github.com/jmoiron/sqlx` – SQL query builder
- `github.com/lib/pq` – PostgreSQL driver
- `github.com/golang-jwt/jwt/v5` – JWT verification
- `github.com/segmentio/kafka-go` – Kafka consumer
- Concurrency: `sync.RWMutex`, `errgroup` – concurrent state management

**StreamStock (Go)**
- `github.com/gorilla/websocket` – WebSocket protocol handling
- `github.com/segmentio/kafka-go` – Kafka consumer
- `net/http` – standard HTTP server
- Concurrency: goroutines, channels – pub/sub pattern

### Infrastructure & protocols

- **HTTP/2** – REST endpoints (InteractionApp)
- **WebSocket (RFC 6455)** – bidirectional real-time (StreamStock)
- **Apache Kafka** – message broker (schema-less JSON payloads)
- **JWT/RSA** – token-based auth (RS256 signature)
- **OpenAPI 3.0** – API specification (`InteractionApp/StockAPI.yaml`)

---

## Architecture overview

```text
                    (tick collector)
                          |
                          v
                    Kafka topic
                     /       \
                    v         v
           StreamStock      InteractionApp
         (WebSocket hub)    (REST API + PriceStore cache)
              |                    |
              v                    v
         WS clients           API consumers
```

### Service responsibilities

- **AuthenApp**: Stateless JWT issuer + user CRUD (MongoDB)
- **InteractionApp**: Stateful REST API (Postgres) + Kafka consumer (PriceStore in-memory)
- **StreamStock**: Event fanout hub (Kafka consumer → WebSocket broadcast by symbol)

### Data flow & Kafka semantics

- Message key = `symbol` (routing key)
- StreamStock subscribes per-symbol (client → `{"type":"subscribe", "symbol":"..."}`)
- In-process event bus: **non-blocking, at-most-once** (buffer overflow → drop tick)
- Backpressure: per-connection buffer (256) → slow clients removed

---

## Operational characteristics

- **Async patterns**: Python async (Motor/Beanie), Go concurrency (errgroup, goroutines)
- **In-memory state**: PriceStore (InteractionApp), WebSocket clients map (StreamStock)
- **Configuration**: Environment variables + `.env` files (12-factor)
- **Security**: PEM-based key pair (AuthenApp), Bearer token enforcement
- **Deployment**: Single `docker-compose.yml` (Postgres only; Kafka/MongoDB external)

---

## License

See `LICENSE`.
