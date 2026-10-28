// Package notify consumes alert_triggered and delivers it to the user's channels.
// It runs off the tick path on purpose: external APIs are slow and flaky, and a
// slow send here only delays notifications, never price evaluation.
package notify

import (
	"alert-engine/model"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"strings"

	"github.com/jmoiron/sqlx"
	"github.com/segmentio/kafka-go"
)

type Notifier struct {
	db       *sqlx.DB
	telegram *Telegram
	email    *Email
}

func NewNotifier(db *sqlx.DB, telegram *Telegram, email *Email) *Notifier {
	return &Notifier{db: db, telegram: telegram, email: email}
}

type channel struct {
	TelegramChatID sql.NullString `db:"telegram_chat_id"`
	Email          sql.NullString `db:"email"`
}

// Handle is the kafkax.MessageHandler for alert_triggered. Returning an error
// makes the listener retry with backoff.
//
// Idempotency: alert_history.notified_at is set after a successful send, and a
// row that already has it is skipped, so replays and outbox duplicates are
// harmless. A retry after a partial failure (Telegram ok, email failed) can
// resend Telegram; a per-channel sent flag would fix that if it matters.
func (n *Notifier) Handle(ctx context.Context, msg kafka.Message) error {
	var event model.AlertTriggered
	if err := json.Unmarshal(msg.Value, &event); err != nil {
		log.Printf("notifier: skip malformed event offset=%d err=%v", msg.Offset, err)
		return nil
	}

	var notified bool
	err := n.db.GetContext(ctx, &notified, `select notified_at is not null from alert_history where id = $1`, event.HistoryID)
	if errors.Is(err, sql.ErrNoRows) {
		log.Printf("notifier: history %s not found, skip", event.HistoryID)
		return nil
	}
	if err != nil {
		return err
	}
	if notified {
		return nil
	}

	var ch channel
	err = n.db.GetContext(ctx, &ch, `select telegram_chat_id, email from notification_channel where user_id = $1`, event.UserID)
	if errors.Is(err, sql.ErrNoRows) {
		log.Printf("notifier: user %s has no notification channel, history %s not delivered", event.UserID, event.HistoryID)
		return nil
	}
	if err != nil {
		return err
	}

	text := FormatMessage(event)
	if ch.TelegramChatID.Valid && n.telegram.Enabled() {
		if err := n.telegram.Send(ctx, ch.TelegramChatID.String, text); err != nil {
			return err
		}
	}
	if ch.Email.Valid && n.email.Enabled() {
		if err := n.email.Send(ctx, ch.Email.String, event); err != nil {
			return err
		}
	}

	_, err = n.db.ExecContext(ctx, `update alert_history set notified_at = now() where id = $1 and notified_at is null`, event.HistoryID)
	if err == nil {
		log.Printf("notifier: delivered history %s to user %s", event.HistoryID, event.UserID)
	}
	return err
}

// FormatMessage renders e.g.
//
//	🔔 AAPL alert triggered at 151.2
//	PRICE > 150 AND VOLUME > 1000000
func FormatMessage(e model.AlertTriggered) string {
	return fmt.Sprintf("🔔 %s alert triggered at %v\n%s\n%s",
		e.Symbol, e.Price, formatConditions(e), e.TriggeredAt.Format("2006-01-02 15:04:05 MST"))
}

// formatConditions renders e.g. "PRICE > 150 AND VOLUME > 1000000".
func formatConditions(e model.AlertTriggered) string {
	conds := make([]string, 0, len(e.Triggers))
	for _, t := range e.Triggers {
		conds = append(conds, fmt.Sprintf("%s %s %v", t.Indicator, t.Operator, t.Threshold))
	}
	return strings.Join(conds, " "+e.Logic+" ")
}
