package mailer

import (
	"context"
	"errors"
	"net/textproto"
	"testing"

	"mail-service/templates"

	"github.com/segmentio/kafka-go"
)

type fakeSender struct {
	err  error
	sent []string
}

func (f *fakeSender) Send(_ context.Context, to, subject, _ string) error {
	f.sent = append(f.sent, to+"|"+subject)
	return f.err
}

func newMailer(t *testing.T, sender *fakeSender) *Mailer {
	t.Helper()
	r, err := templates.New(map[string]any{"app_name": "Kstock"})
	if err != nil {
		t.Fatal(err)
	}
	return New(r, sender)
}

func TestHandle(t *testing.T) {
	valid := `{"id":"1","template":"test_email","to":"an@example.com","data":{"email":"an@example.com"}}`
	tests := []struct {
		name      string
		value     string
		key       string
		sendErr   error
		wantErr   bool
		wantSends int
	}{
		{name: "sends", value: valid, wantSends: 1},
		{name: "recipient from key", value: `{"template":"test_email"}`, key: "k@example.com", wantSends: 1},
		{name: "malformed json is dropped", value: `{`, wantSends: 0},
		{name: "unknown template is dropped", value: `{"template":"nope","to":"an@example.com"}`, wantSends: 0},
		{name: "smtp 5xx is dropped", value: valid, sendErr: &textproto.Error{Code: 550, Msg: "no such user"}, wantSends: 1},
		{name: "smtp 4xx is retried", value: valid, sendErr: &textproto.Error{Code: 421, Msg: "rate limited"}, wantErr: true, wantSends: 1},
		{name: "network error is retried", value: valid, sendErr: errors.New("connection refused"), wantErr: true, wantSends: 1},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			sender := &fakeSender{err: tt.sendErr}
			err := newMailer(t, sender).Handle(context.Background(), kafka.Message{Key: []byte(tt.key), Value: []byte(tt.value)})
			if (err != nil) != tt.wantErr {
				t.Fatalf("err = %v, wantErr %v", err, tt.wantErr)
			}
			if len(sender.sent) != tt.wantSends {
				t.Fatalf("sends = %v, want %d", sender.sent, tt.wantSends)
			}
		})
	}
}
