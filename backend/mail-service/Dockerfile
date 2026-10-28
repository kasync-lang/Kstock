FROM golang:1.26-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/mail-service .

# Final image
FROM gcr.io/distroless/static-debian12:nonroot
WORKDIR /app
COPY --from=builder --chown=nonroot:nonroot /out/mail-service ./mail-service

ENV APP_ENV=production
ENTRYPOINT ["/app/mail-service"]
