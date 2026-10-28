// Package outbox re-publishes alert_history rows whose alert_triggered event
// never reached Kafka (engine crashed or Kafka was down right after the commit).
package outbox

import (
	"context"
	"time"

	"github.com/jmoiron/sqlx"
	"github.com/segmentio/kafka-go"
)

const SweepInterval = 30 * time.Second

type Sweeper struct {
	db     *sqlx.DB
	writer *kafka.Writer
}

func NewSweeper(db *sqlx.DB, writer *kafka.Writer) *Sweeper {
	return &Sweeper{db: db, writer: writer}
}

// Run blocks until ctx is cancelled.
//
// TODO(you): mỗi SweepInterval:
//  1. Query các row chưa publish, bỏ qua row quá mới (engine có thể đang publish nó):
//     select id, snapshot from alert_history
//     where published = false and triggered_at < now() - interval '10 seconds'
//     order by triggered_at limit 100
//  2. Với mỗi row: json.Unmarshal(snapshot, &event), set event.HistoryID = id,
//     rồi engine.Publish(ctx, s.db, s.writer, event).
//     (import "alert-engine/engine" — Publish đã đánh dấu published = true.)
//  3. Lỗi một row thì log rồi đi tiếp, lần sweep sau sẽ thử lại.
//
// Publish lại có thể tạo event trùng (vd. Kafka nhận rồi nhưng update DB lỗi) —
// không sao, notifier chặn trùng bằng alert_history.notified_at.
func (s *Sweeper) Run(ctx context.Context) {
	ticker := time.NewTicker(SweepInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			// TODO(you): s.sweepOnce(ctx)
		}
	}
}
