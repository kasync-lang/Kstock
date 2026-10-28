# Alert Engine

Service Go chấm các alert của người dùng (vd. `AAPL PRICE > 150`) trên từng tick
giá realtime, và khi một alert khớp thì ghi lịch sử rồi gửi thông báo qua
Telegram / Email (email được giao cho `mail-service` qua Kafka).

## Tổng quan

```
                    ┌──────────────────────── alert-engine (1 process) ─────────────────────────┐
                    │                                                                            │
Kafka               │  kafkax.Listen ──▶ engine.HandleTick                                       │
raw_data_trade ─────┼─▶ (group alert-engine)   │                                                 │
                    │                          ├─ indicator.Store.Apply(tick)   (RAM)            │
                    │                          ├─ rules.Index.ForSymbol(symbol) (RAM)            │
                    │                          ├─ engine.Eval(alert, state)                      │
                    │                          └─ khớp ─▶ engine.fire                            │
                    │                                       │ TX: alert.status=false             │
                    │                                       │     + insert alert_history ────────┼──▶ Postgres
                    │                                       └─ engine.Publish ───────────────────┼──▶ Kafka alert_triggered
                    │                                                                            │
                    │  outbox.Sweeper (30s) ── alert_history.published=false ──▶ engine.Publish  │
                    │                                                                            │
Kafka               │  kafkax.Listen ──▶ notify.Notifier.Handle                                  │
alert_triggered ────┼─▶ (group alert-notifier)  ├─ đọc notification_channel                      │
                    │                           ├─ Telegram.Send ────────────────────────────────┼──▶ Telegram API
                    │                           ├─ Email.Send ───────────────────────────────────┼──▶ Kafka email_requests ──▶ mail-service
                    │                           └─ set alert_history.notified_at                 │
                    │                                                                            │
Postgres            │  rules.Sync                                                                │
NOTIFY alert_changed┼─▶ LISTEN ──▶ reload 1 alert ──▶ rules.Index                                │
                    │   mỗi 5 phút / khi reconnect ──▶ reload toàn bộ                            │
                    └────────────────────────────────────────────────────────────────────────────┘
```

Ý tưởng chính:

- **Hot path chỉ dùng RAM.** Mỗi tick chỉ đụng tới map trong bộ nhớ (rules +
  indicators). Database chỉ bị chạm khi một alert thực sự fire.
- **Fire đúng một lần.** Việc "chiếm" alert bằng một `UPDATE ... WHERE status = true`
  có điều kiện đảm bảo chỉ một lần fire được ghi, kể cả khi tick bị replay, service
  restart, hay chạy nhiều instance.
- **Outbox pattern.** `alert_history` vừa là lịch sử vừa là outbox: row nào
  `published = false` là event chưa lên Kafka, sweeper sẽ gửi lại.
- **Gửi thông báo tách khỏi chấm giá.** Telegram/email chậm và hay lỗi, nên nó
  chạy ở consumer riêng (`alert_triggered`). Gửi chậm chỉ làm trễ thông báo, không
  làm trễ việc chấm tick.

## Cấu trúc thư mục

| Đường dẫn | Vai trò |
|---|---|
| `main.go` | Khởi tạo mọi thứ và chạy 4 goroutine: rules sync, outbox sweeper, tick listener, notifier |
| `config.go` | Đọc biến môi trường thành `Config` |
| `model/` | Các struct dùng chung: `Tick`, `Alert`, `Trigger`, `AlertTriggered` |
| `kafkax/` | Consumer (commit sau khi xử lý xong, có retry) và producer đồng bộ |
| `rules/` | Bản sao in-memory của các alert đang active + đồng bộ với Postgres |
| `indicator/` | Giá trị chỉ báo theo từng symbol (PRICE, sau này VOLUME, RSI) |
| `engine/` | Chấm điều kiện và fire alert |
| `outbox/` | Gửi lại các event chưa lên được Kafka |
| `notify/` | Consumer `alert_triggered`, gửi Telegram / Email |

## Từng thành phần

### `main.go` — điểm khởi động

Thứ tự khởi động có chủ đích:

1. Load `.env` (nếu có) và `LoadConfig()`.
2. Tạo context huỷ được bằng `SIGINT`/`SIGTERM`.
3. Kết nối Postgres.
4. **`ruleSync.FullReload` trước khi nhận tick nào** — nếu không, những tick đầu
   tiên sẽ được chấm với một index rỗng và bỏ lỡ alert. Lỗi ở bước này là
   `log.Fatalf`.
5. Tạo Kafka writer (topic `alert_triggered`), `Engine`, `Notifier`.
6. Chạy 4 goroutine qua helper `run(name, fn)` (gắn vào `WaitGroup`):
   - `rules sync` — `ruleSync.Run`
   - `outbox sweeper` — `outbox.Sweeper.Run`
   - `tick listener` — `kafkax.Listen` trên `raw_data_trade`, handler `eng.HandleTick`,
     **không retry** (`MaxRetries` = 0, xem phần engine)
   - `notifier` — `kafkax.Listen` trên `alert_triggered`, handler `notifier.Handle`,
     `MaxRetries: 5`
7. Chờ `ctx.Done()` rồi `wg.Wait()` để các goroutine dừng gọn.

Nếu một trong hai listener trả lỗi cấu hình (thiếu brokers/topic/group), nó gọi
`stop()` để tắt cả service thay vì chạy dở.

### `config.go` — cấu hình

`GetEnv(key, fallback)` coi biến rỗng như không set. `KAFKA_BOOTSTRAP_SERVERS`
được tách theo dấu phẩy. DSN Postgres được ghép từ các biến `POSTGRES_*`
(`sslmode=disable`, `connect_timeout=5`). Danh sách biến ở phần
[Cấu hình](#cấu-hình).

### `model/` — kiểu dữ liệu

- **`Tick`** — một giao dịch từ `raw_data_trade`, cùng shape với `dto.Tick` của
  core-api: `s` symbol, `p` giá, `v` khối lượng, `t` unix **milliseconds**, `c`
  condition codes.
- **`Trigger`** — một điều kiện: `Indicator` (`PRICE`/`VOLUME`/`RSI`), `Operator`
  (`>`, `<`, `>=`, `<=`, `==`, `!=`), `Threshold`, `Position`. Tag `db` map với cột
  của bảng `triggeralert` (`condition`, `value`, ...).
- **`Alert`** — một alert active trong RAM: `ID`, `UserID`, `Symbol`, `Logic`
  (`AND`/`OR`) và danh sách `Triggers`.
- **`AlertTriggered`** — payload đẩy lên `alert_triggered`. `HistoryID` (id của row
  `alert_history`) là **khoá idempotency** cho notifier.

### `kafkax/` — Kafka helpers

**`listener.go` — `Listen(ctx, cfg, handler)`**

Copy pattern từ `core-api/internal/server/EventKafkaListener.go` (copy chứ không
import, để service build độc lập).

- Dùng `kafka.Reader` với consumer group. `StartOffset: LastOffset` chỉ áp dụng khi
  group **chưa có offset đã commit** (lần chạy đầu tiên): bắt đầu từ tick mới nhất,
  không đọc lại lịch sử.
- Vòng lặp: `FetchMessage` → `processWithRetry` → `CommitMessages`. Message chỉ
  được commit **sau khi** handler thành công ⇒ crash giữa chừng thì message được
  xử lý lại (**at-least-once**). Vì vậy mọi handler phải idempotent.
- `processWithRetry`: thử tối đa `MaxRetries + 1` lần, backoff luỹ thừa
  `RetryBackoff * 2^attempt` (mặc định 500ms → 1s → 2s → ...), dừng ngay nếu ctx bị huỷ.
- Hết retry thì log và `continue` mà không commit message đó.

**`writer.go` — `NewWriter(brokers, topic)`**

Producer **đồng bộ**: `RequiredAcks: RequireAll`, nên `WriteMessages` chỉ trả về khi
broker đã ack. Outbox dựa vào điều này: chỉ đánh dấu `published = true` khi chắc
chắn Kafka đã nhận. `Balancer: Hash` + key = `user_id` ⇒ mọi event của cùng một user
vào cùng partition ⇒ giữ đúng thứ tự thông báo cho từng user.

### `rules/` — alert trong bộ nhớ

**`index.go` — `Index`**

Hai map, bảo vệ bởi `sync.RWMutex` (tick loop đọc, sync loop ghi):

- `bySymbol[symbol][alertID] → *Alert` — để mỗi tick chỉ xem alert của đúng symbol đó.
- `symbolOf[alertID] → symbol` — để xoá một alert khi chỉ biết id (NOTIFY chỉ gửi id).

Các thao tác:

- `ReplaceAll` — dựng map mới ở ngoài lock rồi swap một lần (lock ngắn nhất có thể).
- `Upsert` — xoá bản cũ trước rồi thêm, nên alert đổi symbol sẽ được "chuyển" đúng chỗ.
- `Remove` — xoá, và dọn luôn map con của symbol nếu rỗng.
- `ForSymbol` — trả về **slice copy**, nên engine có thể duyệt thoải mái trong khi
  index đang bị sửa (và `fire` có thể gọi `Remove` giữa vòng lặp).

**`repo.go` — `Repo`**

Query `alert JOIN triggeralert`, chỉ lấy alert `status = true` và trigger có đủ
`indicator`, `condition`, `value`. Dùng **inner join** có chủ đích: alert không có
trigger thì không bao giờ fire được nên bỏ luôn.

- `LoadActive` — toàn bộ, `order by a.id, t.position`.
- `LoadOne(id)` — một alert; trả `nil` nếu đã bị xoá hoặc tắt.
- `groupRows` — gom các dòng join (1 dòng/trigger) lại thành 1 `Alert`/id. Yêu cầu
  input đã sắp xếp theo id.

**`sync.go` — `Sync`**

Giữ `Index` khớp với Postgres bằng 3 cơ chế:

| Sự kiện | Hành động |
|---|---|
| `NOTIFY alert_changed '<alert_id>'` | `reloadOne(id)`: còn active → `Upsert`, không → `Remove` |
| `pq.Listener` reconnect (Notify nhận `nil`) | `FullReload` — NOTIFY gửi lúc mất kết nối đã bị mất |
| Ticker mỗi `FullReloadInterval` (5 phút) | `FullReload` — lưới an toàn |

NOTIFY đến từ trigger Postgres trong `alert_notify_trigger.sql` (xem
[Database](#database)), nên bất kỳ ai sửa `alert`/`triggeralert` (core-api, psql
tay, ...) đều được engine thấy ngay mà không cần gọi API nào.

### `indicator/` — trạng thái chỉ báo theo symbol

**`state.go`**

- `Reading{Cur, Prev, HasPrev}` — giá trị hiện tại và giá trị trước lần cập nhật
  gần nhất. `Prev` là thứ cho phép `==` hiểu là "cắt qua ngưỡng".
- `SymbolState` — map `indicator → *Reading` của một symbol. `set()` đẩy `Cur` cũ
  sang `Prev` rồi ghi giá trị mới.
- `OnTick(tick)` — hiện chỉ cập nhật `PRICE = tick.P`.
- `Value(indicator)` — trả `false` nếu chưa có giá trị (vd. RSI đang warm-up). Trigger
  trên giá trị chưa có luôn là `false`.
- `Store` — map `symbol → *SymbolState`, tạo lười khi gặp symbol lần đầu.

**Không có lock**: `Store` chỉ được chạm bởi goroutine xử lý tick (một
`kafka.Reader` phục vụ tuần tự mọi partition được giao). Nếu sau này xử lý song song
theo partition, hãy shard `Store` theo symbol thay vì thêm mutex toàn cục.

**`rsi.go`** — chưa implement, xem [Việc còn lại](#việc-còn-lại).

### `engine/` — chấm điều kiện và fire

**`engine.go` — `HandleTick`**

Handler cho `raw_data_trade`:

1. Parse JSON; tick hỏng thì log và **bỏ qua** (return `nil`, không retry).
2. Nếu tick thiếu `s` thì lấy symbol từ Kafka key.
3. `state := store.Apply(tick)` — cập nhật chỉ báo.
4. Với mỗi alert của symbol: `Eval` đúng → `fire`.

Luôn trả `nil`, kể cả khi `fire` lỗi. Lý do: nếu trả lỗi, listener sẽ retry và
**áp cùng một tick vào indicator lần nữa**, làm `Prev == Cur` và phá logic "cắt
ngưỡng" của `==`. Đó cũng là lý do tick listener chạy với `MaxRetries = 0`.

**`evaluate.go` — `Eval`**

- Alert không có trigger → `false`.
- `OR`: chỉ cần một trigger đúng (thoát sớm). `AND` (và mọi logic lạ, khớp mặc định
  của core-api): cần tất cả đúng.
- `compare`: `>`, `<`, `>=`, `<=`, `!=` so sánh `Cur` với ngưỡng như bình thường.
- **`==` đặc biệt**: giá là float và nhảy cóc, nên gần như không bao giờ bằng đúng
  ngưỡng. `==` fire khi `Cur == thr` **hoặc** giá vừa cắt qua ngưỡng giữa `Prev` và
  `Cur` (`Prev < thr < Cur` hoặc `Prev > thr > Cur`). Tick đầu tiên của symbol
  (chưa có `Prev`) chỉ fire khi bằng đúng.
- Operator không biết → `false`.

**`fire.go` — `fire` và `Publish`**

`fire(alert, tick)`:

1. `index.Remove(alert.ID)` ngay — các tick sau trong cùng batch không thử fire lại.
2. Dựng `AlertTriggered` (giá = `tick.P`, `TriggeredAt` = thời điểm của tick, UTC)
   và marshal làm `snapshot`.
3. **Transaction**:
   - `UPDATE alert SET status = false WHERE id = $1 AND status = true`.
     `RowsAffected == 0` ⇒ đã có ai fire/tắt rồi ⇒ dừng. Đây là chốt chặn
     "fire đúng một lần".
   - `INSERT INTO alert_history ... RETURNING id` → `HistoryID`.
   - Commit.
4. Sau commit: `Publish`. Lỗi thì chỉ log — row vẫn `published = false`, sweeper sẽ lo.

Alert là **one-shot**: fire xong thì `status = false`. Muốn nhận lại thì người dùng
bật lại alert (core-api set `status = true` → NOTIFY → engine nạp lại).

`Publish(event)` (dùng chung với sweeper): gửi lên Kafka với key = `user_id`, sau đó
`UPDATE alert_history SET published = true`. Nếu Kafka nhận rồi mà update DB lỗi thì
event có thể bị gửi trùng — chấp nhận được vì notifier idempotent.

### `outbox/` — Sweeper

Mỗi `SweepInterval` (30s) lẽ ra sẽ tìm các row `published = false` cũ hơn 10 giây
(để không tranh với engine đang publish) và gọi lại `engine.Publish`. **Hiện mới có
khung**, `sweepOnce` chưa được viết — xem [Việc còn lại](#việc-còn-lại).

### `notify/` — gửi thông báo

**`consumer.go` — `Notifier.Handle`**

Handler cho `alert_triggered` (retry tối đa 5 lần với backoff):

1. Parse event; hỏng thì bỏ qua.
2. `alert_history.notified_at` đã có ⇒ đã gửi rồi ⇒ bỏ qua (**idempotency**: chống
   replay Kafka và event trùng từ outbox). Không thấy history ⇒ bỏ qua.
3. Đọc `notification_channel` của user. Không có ⇒ log và bỏ qua (không retry).
4. `FormatMessage` rồi gửi:
   - Telegram nếu user có `telegram_chat_id` **và** bot token được cấu hình.
   - Email nếu user có `email`: publish request `alert_triggered` lên `email_requests`,
     `mail-service` render template và gửi qua SMTP.
   - Lỗi gửi ⇒ trả lỗi ⇒ listener retry.
5. `UPDATE alert_history SET notified_at = now() WHERE ... AND notified_at IS NULL`.

Hạn chế đã biết: nếu Telegram thành công mà Email lỗi, lần retry sẽ gửi Telegram lần
nữa. Muốn tránh thì cần cờ "đã gửi" riêng cho từng kênh.

Mẫu tin nhắn:

```
🔔 AAPL alert triggered at 151.2
PRICE > 150 AND VOLUME > 1000000
2026-10-26 14:30:05 UTC
```

**`telegram.go`** — gọi `POST https://api.telegram.org/bot<token>/sendMessage`, timeout
10s, status khác 200 thì trả lỗi kèm tối đa 512 byte body. `Enabled()` = có token.
User lấy `chat_id` bằng cách nhắn cho bot rồi xem
`https://api.telegram.org/bot<token>/getUpdates`.

**`email.go`** — không đụng tới SMTP. `Send` publish
`{id: history_id, template: "alert_triggered", to, data: {symbol, price, conditions, triggered_at}}`
lên `email_requests` (key = địa chỉ email) và trả về khi Kafka đã ack. Lỗi publish được
notifier retry như lỗi Telegram. Việc gửi thật, retry SMTP và template HTML nằm ở
`backend/mail-service`.

## Database

Các bảng trong Postgres `interactdb` (DDL ở `backend/core-api/docs/public/`):

| Bảng | Chủ sở hữu | Engine dùng để |
|---|---|---|
| `alert` | core-api | đọc alert active; `status = false` khi fire |
| `triggeralert` | core-api | đọc điều kiện (`indicator`, `condition`, `value`, `position`) |
| `alert_history` | alert-engine | lịch sử fire + outbox (`published`) + idempotency notifier (`notified_at`) |
| `notification_channel` | alert-engine | `telegram_chat_id`, `email` của user (email gốc nằm ở auth-service/MongoDB nên giữ bản sao ở đây) |

Trigger `alert_changed_notify` / `triggeralert_changed_notify`
(`alert_notify_trigger.sql`) gọi `pg_notify('alert_changed', <alert_id>)` sau mỗi
insert/update/delete. `pg_notify` chỉ được gửi khi transaction commit, và payload
trùng trong cùng transaction được gộp làm một — nên sửa một alert kèm 3 trigger chỉ
sinh 1 lần reload.

Lưu ý: chính `fire` cũng update `alert` nên cũng sinh NOTIFY; khi đó `LoadOne` trả
`nil` và `Remove` chạy lần nữa — vô hại.

Áp migration (idempotent, chạy lại được):

```bash
psql -h localhost -U postgres -d interactdb \
  -f backend/core-api/docs/public/migrations/20261024_alert_engine.sql
```

## Kafka

| Topic | Vai trò | Consumer group | Key |
|---|---|---|---|
| `raw_data_trade` | tick đầu vào | `alert-engine` | symbol |
| `alert_triggered` | event alert đã fire | `alert-notifier` | `user_id` |

Payload `alert_triggered`:

```json
{
  "history_id": "8f6c...",
  "alert_id": "2b1e...",
  "user_id": "u123",
  "symbol": "AAPL",
  "price": 151.2,
  "logic": "AND",
  "triggers": [{"indicator": "PRICE", "operator": ">", "threshold": 150, "position": 0}],
  "triggered_at": "2026-10-26T14:30:05Z"
}
```

## Đảm bảo giao nhận

| Tình huống | Điều gì xảy ra |
|---|---|
| Tick bị replay (crash trước khi commit offset) | `UPDATE ... AND status = true` trả 0 dòng ⇒ không fire lần 2 |
| Chạy 2 instance engine | Như trên, chỉ instance thắng `UPDATE` ghi history |
| Crash sau commit DB, trước khi lên Kafka | Row `published = false` ⇒ sweeper gửi lại (khi đã implement) |
| Kafka nhận nhưng update `published` lỗi | Event có thể trùng ⇒ notifier bỏ qua nhờ `notified_at` |
| Telegram / Kafka lỗi tạm thời | Notifier retry 5 lần với backoff |
| SMTP lỗi tạm thời | `mail-service` tự retry, không ảnh hưởng alert-engine |
| Mất kết nối LISTEN | Reconnect tự động + full reload; thêm full reload mỗi 5 phút |

## Cấu hình

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:29092` | danh sách broker, phân cách bằng dấu phẩy |
| `KAFKA_TICK_TOPIC` | `raw_data_trade` | topic tick |
| `KAFKA_GROUP_ID` | `alert-engine` | group đọc tick |
| `KAFKA_TRIGGERED_TOPIC` | `alert_triggered` | topic event fire |
| `KAFKA_NOTIFIER_GROUP_ID` | `alert-notifier` | group của notifier |
| `POSTGRES_HOST` / `PORT` / `USER` / `PASSWORD` / `DB` | `localhost` / `5432` / `postgres` / `postgres` / `interactdb` | kết nối Postgres |
| `TELEGRAM_BOT_TOKEN` | rỗng | rỗng = tắt kênh Telegram |
| `KAFKA_EMAIL_TOPIC` | `email_requests` | topic yêu cầu gửi mail của `mail-service` |

## Chạy

Local (cần Postgres đã chạy migration và Kafka):

```bash
cd backend/alert-engine
cp .env.example .env
go run .
go test ./...
```

Docker Compose: service `alert-engine` trong `docker-compose.yml` ở root, chờ
`postgres` healthy và `kafka-init` xong. Image build 2 stage, chạy bằng
`distroless/static:nonroot`.

Thử nhanh: tạo một alert `PRICE > <giá hiện tại thấp hơn một chút>` cho một symbol
đang có tick, thêm `notification_channel` cho user, rồi xem log
`engine: fired alert ...` và `notifier: delivered history ...`.

## Việc còn lại

| Chỗ | Trạng thái | Gợi ý |
|---|---|---|
| `indicator/state.go` — `VOLUME` | TODO | cộng dồn `tick.V` theo ngày giao dịch (giờ `America/New_York`), reset khi sang ngày |
| `indicator/rsi.go` — `RSI` | TODO | RSI(14) Wilder trên nến 1m dựng từ tick; warm-up từ ClickHouse `aggregate_db.ohlcv_1m` |
| `outbox/sweeper.go` — `sweepOnce` | TODO | query row `published = false` cũ hơn 10s, `limit 100`, gọi `engine.Publish` |

Cho tới khi VOLUME/RSI xong, mọi trigger trên hai chỉ báo này luôn là `false` (vì
`Value` trả `false`), nên alert `AND` có chứa chúng sẽ không bao giờ fire.

## Những điểm cần lưu ý

- **`fire` lỗi DB làm alert biến khỏi index tới 5 phút.** `fire` gọi
  `index.Remove` *trước* transaction. Nếu transaction lỗi (DB chập chờn) thì không có
  `UPDATE` nào nên không có NOTIFY; alert chỉ quay lại ở lần full reload kế tiếp. Comment
  trong `HandleTick` ("the next tick re-evaluates the alert anyway") vì thế chưa đúng
  hẳn. Cách sửa: `Upsert` lại alert khi `fire` trả lỗi.
- **Notifier hết retry vẫn có thể mất message.** Listener `continue` mà không commit,
  nhưng offset của Kafka là con trỏ: khi message *sau* được commit thì message lỗi
  cũng coi như đã qua. Row `alert_history` lúc đó có `published = true` nhưng
  `notified_at` null — có thể dùng điều kiện này để quét gửi lại, hoặc đẩy sang
  dead-letter topic.
- **Indicator nằm trong RAM.** Restart thì mất `Prev`, nên tick đầu tiên sau restart
  không thể kích hoạt `==` theo kiểu cắt ngưỡng.
