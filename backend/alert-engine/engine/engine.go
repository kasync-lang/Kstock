package engine

import (
	"alert-engine/indicator"
	"alert-engine/model"
	"alert-engine/rules"
	"context"
	"encoding/json"
	"log"

	"github.com/jmoiron/sqlx"
	"github.com/segmentio/kafka-go"
)

type Engine struct {
	index  *rules.Index
	state  *indicator.Store
	db     *sqlx.DB
	writer *kafka.Writer
}

func New(index *rules.Index, db *sqlx.DB, writer *kafka.Writer) *Engine {
	return &Engine{index: index, state: indicator.NewStore(), db: db, writer: writer}
}

// HandleTick is the kafkax.MessageHandler for raw_data_trade. Hot path: memory
// only, the database is touched only when an alert actually fires.
//
// It never returns an error for a failed fire: the retry would re-apply the same
// tick to the indicators (breaking Prev), and the next tick re-evaluates the
// alert anyway since it stays in the index until it fires.
func (e *Engine) HandleTick(ctx context.Context, msg kafka.Message) error {
	var tick model.Tick
	if err := json.Unmarshal(msg.Value, &tick); err != nil {
		log.Printf("engine: skip malformed tick offset=%d err=%v", msg.Offset, err)
		return nil
	}
	if tick.S == "" {
		tick.S = string(msg.Key)
	}

	state := e.state.Apply(tick)
	for _, alert := range e.index.ForSymbol(tick.S) {
		if !Eval(alert, state) {
			continue
		}
		if err := e.fire(ctx, alert, tick); err != nil {
			log.Printf("engine: fire alert %s failed: %v", alert.ID, err)
		}
	}
	return nil
}
