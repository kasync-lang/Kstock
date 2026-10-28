// Package smtp sends one HTML email per call over SMTP. It is written for Gmail
// with an app password (smtp.gmail.com:587, STARTTLS) but works with any server,
// including Mailpit for local testing (no TLS, no auth).
package smtp

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/tls"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"mime"
	"net"
	"net/mail"
	"net/smtp"
	"net/textproto"
	"strings"
	"time"
)

type Config struct {
	Host     string
	Port     string
	User     string
	Password string // Gmail: a 16-character app password, not the account password
	From     string
	FromName string
	Timeout  time.Duration
}

type Sender struct {
	cfg  Config
	from mail.Address
}

func NewSender(cfg Config) (*Sender, error) {
	if cfg.Host == "" || cfg.From == "" {
		return nil, errors.New("smtp: host and from are required")
	}
	from, err := mail.ParseAddress(cfg.From)
	if err != nil {
		return nil, fmt.Errorf("smtp: invalid from address: %w", err)
	}
	if cfg.FromName != "" {
		from.Name = cfg.FromName
	}
	if cfg.Timeout <= 0 {
		cfg.Timeout = 30 * time.Second
	}
	return &Sender{cfg: cfg, from: *from}, nil
}

// ErrInvalidRecipient means the address can never be delivered to; retrying is pointless.
var ErrInvalidRecipient = errors.New("invalid recipient")

// ErrAuth means the server rejected SMTP_USER/SMTP_PASSWORD. It is a problem
// with the service, not with the email, so it is never permanent for the email.
var ErrAuth = errors.New("smtp authentication failed")

// IsPermanent reports whether retrying the same email cannot succeed: a bad
// recipient or an SMTP 5xx reply. 4xx replies (Gmail rate limits included),
// network errors and ErrAuth are not.
func IsPermanent(err error) bool {
	if errors.Is(err, ErrAuth) {
		return false
	}
	if errors.Is(err, ErrInvalidRecipient) {
		return true
	}
	var tpErr *textproto.Error
	return errors.As(err, &tpErr) && tpErr.Code >= 500
}

// Send delivers one email. The whole SMTP conversation is bounded by ctx and
// cfg.Timeout, whichever ends first.
func (s *Sender) Send(ctx context.Context, to, subject, htmlBody string) error {
	rcpt, err := mail.ParseAddress(to)
	if err != nil {
		return fmt.Errorf("%w %q: %v", ErrInvalidRecipient, to, err)
	}
	msg, err := s.buildMessage(*rcpt, subject, htmlBody)
	if err != nil {
		return err
	}

	ctx, cancel := context.WithTimeout(ctx, s.cfg.Timeout)
	defer cancel()

	addr := net.JoinHostPort(s.cfg.Host, s.cfg.Port)
	dialer := &net.Dialer{}
	conn, err := dialer.DialContext(ctx, "tcp", addr)
	if err != nil {
		return fmt.Errorf("smtp dial %s: %w", addr, err)
	}
	// net/smtp has no context support: a deadline on the socket bounds every
	// read/write, and closing it on cancel unblocks whatever is in flight.
	if deadline, ok := ctx.Deadline(); ok {
		_ = conn.SetDeadline(deadline)
	}
	stop := context.AfterFunc(ctx, func() { conn.Close() })
	defer stop()

	tlsConfig := &tls.Config{ServerName: s.cfg.Host, MinVersion: tls.VersionTLS12}
	if s.cfg.Port == "465" {
		conn = tls.Client(conn, tlsConfig)
	}

	c, err := smtp.NewClient(conn, s.cfg.Host)
	if err != nil {
		conn.Close()
		return fmt.Errorf("smtp handshake: %w", err)
	}
	defer c.Close()

	if ok, _ := c.Extension("STARTTLS"); ok && s.cfg.Port != "465" {
		if err := c.StartTLS(tlsConfig); err != nil {
			return fmt.Errorf("smtp starttls: %w", err)
		}
	}
	if s.cfg.User != "" {
		if err := c.Auth(smtp.PlainAuth("", s.cfg.User, s.cfg.Password, s.cfg.Host)); err != nil {
			return fmt.Errorf("%w: %w", ErrAuth, err)
		}
	}
	if err := c.Mail(s.from.Address); err != nil {
		return fmt.Errorf("smtp MAIL FROM: %w", err)
	}
	if err := c.Rcpt(rcpt.Address); err != nil {
		return fmt.Errorf("smtp RCPT TO: %w", err)
	}
	w, err := c.Data()
	if err != nil {
		return fmt.Errorf("smtp DATA: %w", err)
	}
	if _, err := w.Write(msg); err != nil {
		return fmt.Errorf("smtp write: %w", err)
	}
	if err := w.Close(); err != nil {
		return fmt.Errorf("smtp end of data: %w", err)
	}
	return c.Quit()
}

// buildMessage renders RFC 5322 headers and a base64 HTML body. Base64 keeps
// lines under SMTP's 998-byte limit; the compiled MJML templates are one long line.
func (s *Sender) buildMessage(to mail.Address, subject, htmlBody string) ([]byte, error) {
	var b bytes.Buffer
	header := func(k, v string) { fmt.Fprintf(&b, "%s: %s\r\n", k, v) }

	header("From", s.from.String())
	header("To", to.String())
	header("Subject", mime.QEncoding.Encode("utf-8", strings.ReplaceAll(subject, "\n", " ")))
	header("Date", time.Now().Format(time.RFC1123Z))
	id, err := messageID(s.from.Address)
	if err != nil {
		return nil, err
	}
	header("Message-ID", id)
	header("MIME-Version", "1.0")
	header("Content-Type", `text/html; charset="UTF-8"`)
	header("Content-Transfer-Encoding", "base64")
	b.WriteString("\r\n")

	encoded := base64.StdEncoding.EncodeToString([]byte(htmlBody))
	for len(encoded) > 76 {
		b.WriteString(encoded[:76] + "\r\n")
		encoded = encoded[76:]
	}
	b.WriteString(encoded + "\r\n")
	return b.Bytes(), nil
}

func messageID(from string) (string, error) {
	buf := make([]byte, 16)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	domain := "localhost"
	if at := strings.LastIndex(from, "@"); at >= 0 {
		domain = from[at+1:]
	}
	return fmt.Sprintf("<%s@%s>", hex.EncodeToString(buf), domain), nil
}
