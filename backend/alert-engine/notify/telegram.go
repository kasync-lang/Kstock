package notify

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type Telegram struct {
	token  string
	client *http.Client
}

func NewTelegram(token string) *Telegram {
	return &Telegram{token: token, client: &http.Client{Timeout: 10 * time.Second}}
}

func (t *Telegram) Enabled() bool { return t.token != "" }

// Send posts a plain-text message to a chat. The user gets their chat id by
// messaging the bot, then reading it from https://api.telegram.org/bot<token>/getUpdates.
func (t *Telegram) Send(ctx context.Context, chatID, text string) error {
	body, err := json.Marshal(map[string]string{"chat_id": chatID, "text": text})
	if err != nil {
		return err
	}
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", t.token)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := t.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		detail, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return fmt.Errorf("telegram: status %d: %s", resp.StatusCode, detail)
	}
	return nil
}
