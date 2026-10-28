# Mail Service

Service Go duy nhất trong Kstock được giữ thông tin đăng nhập SMTP. Các backend khác
không tự gửi mail: chúng publish một yêu cầu `{template, to, data}` lên Kafka, còn
mail-service render template và gửi qua Gmail (app password).

```
auth-service ─┐
              ├──▶ Kafka email_requests ──▶ mailer.Handle ──▶ templates.Render ──▶ smtp.Send ──▶ Gmail
alert-engine ─┘     (group mail-service)
```

## Contract: topic `email_requests`

Key = địa chỉ người nhận. Value:

```json
{
  "id": "6f1c0e8a-...",
  "template": "reset_password",
  "to": "user@example.com",
  "data": { "username": "user@example.com", "link": "http://localhost:5173/reset-password?token=...", "valid_hours": 1 },
  "created_at": "2026-10-27T10:00:00Z"
}
```

- `id` chỉ dùng để log và dò lỗi. auth-service sinh UUID; alert-engine dùng `alert_history.id`.
- Caller **không** gửi subject hay HTML. Cả hai được render từ template.
- Mọi template nhận thêm các giá trị mặc định: `app_name`, `project_name` (= `MAIL_FROM_NAME`),
  `support_email`, `logo_url`, `year`. Nếu `data` có key trùng tên thì `data` thắng.

### Templates

| Template | Người gửi | Field trong `data` |
|---|---|---|
| `verify_email` | auth-service `/signup` | `username`, `verify_link`, `expiry_hours` |
| `reset_password` | auth-service `/password-recovery/{email}` | `username`, `link`, `valid_hours` |
| `new_account` | auth-service `POST /user/` (admin tạo user) | `username`, `password`, `link` |
| `test_email` | auth-service `/utils/test-email/` | `email` |
| `alert_triggered` | alert-engine notifier | `symbol`, `price`, `conditions`, `triggered_at` |

Thêm template mới:

1. Đặt file HTML vào `templates/html/`, dùng cú pháp Go `{{.field}}`.
2. Đăng ký tên, subject và file trong `spec` (`templates/templates.go`).
3. Thêm data mẫu vào `sampleData` (`templates/templates_test.go`); test sẽ báo lỗi nếu thiếu.

Body được render bằng `html/template`, nên dữ liệu người dùng tự được escape. Lưu ý
`html/template` cũng xoá comment HTML, kể cả các khối `<!--[if mso]>` mà MJML sinh ra
cho Outlook desktop. Gmail và các client web không bị ảnh hưởng. File nguồn MJML nằm ở
`templates/src/`.

## Xử lý lỗi

Listener chỉ commit offset sau khi handler xử lý xong (at-least-once), retry tối đa 5 lần
với backoff 2s → 4s → … → 32s.

| Lỗi | Hành động |
|---|---|
| JSON hỏng, template không tồn tại, địa chỉ không hợp lệ | log `drop` và bỏ qua: retry cũng không thành công |
| SMTP 5xx (vd. `550 no such user`) | log `drop` và bỏ qua |
| Sai `SMTP_USER`/`SMTP_PASSWORD` (`535`) | service **thoát** mà không commit offset; Docker restart lại, mail vẫn nằm trong Kafka và được gửi khi cấu hình đúng |
| SMTP 4xx (Gmail rate limit `421`/`454`), lỗi mạng, timeout | trả error, listener retry |

Nếu service crash sau khi gửi nhưng trước khi commit offset, mail đó có thể bị gửi lại
một lần. Mình chấp nhận rủi ro này. Nếu cần chặn trùng tuyệt đối, có thể đánh dấu `id`
đã gửi trong Redis (`SETNX mail:sent:<id>`).

## Cấu hình

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:29092` | danh sách broker |
| `KAFKA_EMAIL_TOPIC` | `email_requests` | topic yêu cầu gửi mail |
| `KAFKA_GROUP_ID` | `mail-service` | consumer group |
| `SMTP_HOST` / `SMTP_PORT` | `smtp.gmail.com` / `587` | `587` dùng STARTTLS, `465` dùng TLS trực tiếp |
| `SMTP_USER` | rỗng | địa chỉ Gmail; để rỗng nếu server không cần auth (Mailpit) |
| `SMTP_PASSWORD` | rỗng | **app password** 16 ký tự, không phải mật khẩu Gmail |
| `MAIL_FROM` | `SMTP_USER` | địa chỉ người gửi; với Gmail phải là chính tài khoản đó hoặc alias đã xác minh |
| `MAIL_FROM_NAME` | `Kstock` | tên hiển thị, đồng thời là `app_name` trong template |
| `MAIL_SUPPORT_EMAIL` | `MAIL_FROM` | hiện trong footer của `verify_email` |
| `MAIL_LOGO_URL` | rỗng | logo của `verify_email`; để rỗng thì ẩn |

Nếu `MAIL_FROM` (và `SMTP_USER`) rỗng, service sẽ không consume gì. Request nằm chờ trong
Kafka và được gửi khi bạn cấu hình xong rồi restart.

### Tạo Gmail app password

1. Bật xác minh 2 bước cho tài khoản Google.
2. Vào https://myaccount.google.com/apppasswords, tạo một app password (vd. tên "Kstock").
3. `SMTP_USER=<gmail>`, `SMTP_PASSWORD=<16 ký tự, bỏ dấu cách>`.

Gmail cá nhân giới hạn khoảng 500 người nhận mỗi ngày. Vượt mức sẽ nhận lỗi 4xx/5xx từ
Gmail. Nếu cần gửi nhiều hơn thì chuyển sang Google Workspace hoặc một dịch vụ như SES,
Postmark... và chỉ cần đổi `SMTP_*`.

## Chạy

```bash
cd backend/mail-service
cp .env.example .env   # điền SMTP_USER, SMTP_PASSWORD
go run .
go test ./...
```

Test local không cần Gmail, dùng Mailpit:

```bash
SMTP_HOST=mailpit SMTP_PORT=1025 SMTP_USER= MAIL_FROM=dev@kstock.local \
  docker compose --profile dev-mail up -d mailpit mail-service
# mở http://localhost:8025
```

Gửi tay một request:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 --topic email_requests
{"id":"manual-1","template":"test_email","to":"me@example.com","data":{"email":"me@example.com"}}
```

## Cấu trúc

| Đường dẫn | Vai trò |
|---|---|
| `main.go`, `config.go` | đọc cấu hình, nạp template, chạy listener |
| `kafkax/listener.go` | copy từ alert-engine: commit sau khi xử lý, retry với backoff |
| `model/` | `EmailRequest` |
| `templates/` | các file HTML được embed, registry `spec`, `Renderer` |
| `smtp/` | gửi một mail: STARTTLS/TLS, PlainAuth, header MIME, body base64; `IsPermanent` để phân loại lỗi |
| `mailer/` | handler Kafka: parse → render → send, quyết định drop hay retry |
