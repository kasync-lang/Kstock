package engine

import (
	"alert-engine/model"
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/jmoiron/sqlx"
	"github.com/segmentio/kafka-go"
)

// fire turns a matched alert into exactly one alert_history row and one
// alert_triggered event.
//
//  1. TX: claim the alert (status true -> false) and insert the history row.
//     The conditional UPDATE is what guarantees "fire once": a replayed tick, a
//     restart or a second engine instance gets RowsAffected == 0 and stops here.
//  2. After commit, publish to Kafka and mark the row published. If the publish
//     fails the row stays published = false and outbox.Sweeper retries it.
func (e *Engine) fire(ctx context.Context, alert *model.Alert, tick model.Tick) error {
	// Leave the index first so later ticks in this batch don't try again; the
	// NOTIFY from our own UPDATE would remove it anyway.
	e.index.Remove(alert.ID)

	event := model.AlertTriggered{
		AlertID:     alert.ID,
		UserID:      alert.UserID,
		Symbol:      alert.Symbol,
		Price:       tick.P,
		Logic:       alert.Logic,
		Triggers:    alert.Triggers,
		TriggeredAt: time.UnixMilli(tick.T).UTC(),
	}
	snapshot, err := json.Marshal(event)
	if err != nil {
		return err
	}

	tx, err := e.db.BeginTxx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()

	res, err := tx.ExecContext(ctx, `update alert set status = false, updated_at = now() where id = $1 and status = true`, alert.ID)
	if err != nil {
		return err
	}
	if n, err := res.RowsAffected(); err != nil {
		return err
	} else if n == 0 {
		log.Printf("engine: alert %s already fired or disabled, skip", alert.ID)
		return nil
	}

	err = tx.GetContext(ctx, &event.HistoryID,
		`insert into alert_history (alert_id, user_id, symbol, triggered_price, snapshot, triggered_at)
values ($1, $2, $3, $4, $5, $6) returning id`,
		alert.ID, alert.UserID, alert.Symbol, tick.P, snapshot, event.TriggeredAt)
	if err != nil {
		return err
	}
	if err := tx.Commit(); err != nil {
		return err
	}
	log.Printf("engine: fired alert %s %s price=%v history=%s", alert.ID, alert.Symbol, tick.P, event.HistoryID)

	if err := Publish(ctx, e.db, e.writer, event); err != nil {
		log.Printf("engine: publish history %s failed, sweeper will retry: %v", event.HistoryID, err)
	}
	return nil
}

// Publish sends the event (keyed by user so one user's notifications stay in
// order) and marks its history row as published. Shared with outbox.Sweeper.
func Publish(ctx context.Context, db *sqlx.DB, writer *kafka.Writer, event model.AlertTriggered) error {
	payload, err := json.Marshal(event)
	if err != nil {
		return err
	}
	if err := writer.WriteMessages(ctx, kafka.Message{Key: []byte(event.UserID), Value: payload}); err != nil {
		return err
	}
	_, err = db.ExecContext(ctx, `update alert_history set published = true where id = $1`, event.HistoryID)
	return err
}
