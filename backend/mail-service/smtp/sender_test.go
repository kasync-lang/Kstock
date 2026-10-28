package smtp

import (
	"bufio"
	"context"
	"encoding/base64"
	"errors"
	"fmt"
	"net"
	"net/textproto"
	"strings"
	"testing"
	"time"
)

// fakeServer speaks just enough SMTP for net/smtp (no TLS, no auth). rcptReply
// is what it answers to RCPT TO, so tests can simulate 4xx/5xx failures.
type fakeServer struct {
	addr      string
	rcptReply string
	data      chan string
}

func startFakeServer(t *testing.T, rcptReply string) *fakeServer {
	t.Helper()
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { ln.Close() })
	s := &fakeServer{addr: ln.Addr().String(), rcptReply: rcptReply, data: make(chan string, 1)}
	go func() {
		conn, err := ln.Accept()
		if err != nil {
			return
		}
		defer conn.Close()
		s.serve(conn)
	}()
	return s
}

func (s *fakeServer) serve(conn net.Conn) {
	r := bufio.NewReader(conn)
	reply := func(line string) { conn.Write([]byte(line + "\r\n")) }
	reply("220 fake ESMTP")
	for {
		line, err := r.ReadString('\n')
		if err != nil {
			return
		}
		cmd := strings.ToUpper(strings.TrimSpace(line))
		switch {
		case strings.HasPrefix(cmd, "EHLO"), strings.HasPrefix(cmd, "HELO"):
			reply("250 fake")
		case strings.HasPrefix(cmd, "MAIL FROM"):
			reply("250 ok")
		case strings.HasPrefix(cmd, "RCPT TO"):
			reply(s.rcptReply)
		case cmd == "DATA":
			reply("354 go ahead")
			var b strings.Builder
			for {
				l, err := r.ReadString('\n')
				if err != nil {
					return
				}
				if l == ".\r\n" {
					break
				}
				b.WriteString(l)
			}
			s.data <- b.String()
			reply("250 queued")
		case cmd == "QUIT":
			reply("221 bye")
			return
		default:
			reply("250 ok")
		}
	}
}

func newTestSender(t *testing.T, addr string) *Sender {
	t.Helper()
	host, port, _ := net.SplitHostPort(addr)
	s, err := NewSender(Config{Host: host, Port: port, From: "kstock@gmail.com", FromName: "Kstock", Timeout: 5 * time.Second})
	if err != nil {
		t.Fatal(err)
	}
	return s
}

func TestSendDeliversMessage(t *testing.T) {
	srv := startFakeServer(t, "250 ok")
	err := newTestSender(t, srv.addr).Send(context.Background(), "an@example.com", "Khôi phục mật khẩu", "<b>xin chào</b>")
	if err != nil {
		t.Fatalf("Send: %v", err)
	}

	msg := <-srv.data
	headers, body, _ := strings.Cut(msg, "\r\n\r\n")
	for _, want := range []string{
		`From: "Kstock" <kstock@gmail.com>`,
		"To: <an@example.com>",
		"Subject: =?utf-8?q?",
		`Content-Type: text/html; charset="UTF-8"`,
		"Content-Transfer-Encoding: base64",
	} {
		if !strings.Contains(headers, want) {
			t.Errorf("headers lack %q:\n%s", want, headers)
		}
	}
	decoded, err := base64.StdEncoding.DecodeString(strings.ReplaceAll(body, "\r\n", ""))
	if err != nil {
		t.Fatalf("decode body: %v", err)
	}
	if string(decoded) != "<b>xin chào</b>" {
		t.Fatalf("body = %q", decoded)
	}
}

func TestSendClassifiesErrors(t *testing.T) {
	tests := []struct {
		name      string
		rcptReply string
		permanent bool
	}{
		{"mailbox does not exist", "550 5.1.1 no such user", true},
		{"rate limited", "451 4.3.0 try again later", false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			srv := startFakeServer(t, tt.rcptReply)
			err := newTestSender(t, srv.addr).Send(context.Background(), "an@example.com", "s", "b")
			if err == nil {
				t.Fatal("Send succeeded, want error")
			}
			if got := IsPermanent(err); got != tt.permanent {
				t.Fatalf("IsPermanent(%v) = %v, want %v", err, got, tt.permanent)
			}
		})
	}
}

func TestSendRejectsInvalidRecipient(t *testing.T) {
	s := newTestSender(t, "127.0.0.1:1")
	err := s.Send(context.Background(), "not an address\r\nBcc: x@y.z", "s", "b")
	if !errors.Is(err, ErrInvalidRecipient) || !IsPermanent(err) {
		t.Fatalf("err = %v, want permanent ErrInvalidRecipient", err)
	}
}

func TestNetworkErrorIsTemporary(t *testing.T) {
	ln, _ := net.Listen("tcp", "127.0.0.1:0")
	addr := ln.Addr().String()
	ln.Close() // nothing listens here any more

	err := newTestSender(t, addr).Send(context.Background(), "an@example.com", "s", "b")
	if err == nil || IsPermanent(err) {
		t.Fatalf("err = %v, want temporary error", err)
	}
}

func TestAuthErrorIsNotPermanent(t *testing.T) {
	err := fmt.Errorf("%w: %w", ErrAuth, &textproto.Error{Code: 535, Msg: "bad credentials"})
	if IsPermanent(err) {
		t.Fatal("auth failure must not drop the email")
	}
}
