package rules

import (
	"context"
	"log"
	"time"

	"github.com/lib/pq"
)

const (
	notifyChannel      = "alert_changed"
	FullReloadInterval = 5 * time.Minute
)

// Sync keeps the Index in step with Postgres:
//   - LISTEN alert_changed -> reload just that alert (trigger in alert_notify_trigger.sql)
//   - on (re)connect and every FullReloadInterval -> reload everything, because
//     notifications sent while we were disconnected are lost.
type Sync struct {
	repo  *Repo
	index *Index
	dsn   string
}

func NewSync(repo *Repo, index *Index, dsn string) *Sync {
	return &Sync{repo: repo, index: index, dsn: dsn}
}

func (s *Sync) FullReload(ctx context.Context) error {
	alerts, err := s.repo.LoadActive(ctx)
	if err != nil {
		return err
	}
	s.index.ReplaceAll(alerts)
	log.Printf("rules sync: full reload, %d active alerts", len(alerts))
	return nil
}

func (s *Sync) reloadOne(ctx context.Context, id string) {
	alert, err := s.repo.LoadOne(ctx, id)
	if err != nil {
		log.Printf("rules sync: reload alert %s failed: %v", id, err)
		return
	}
	if alert == nil {
		s.index.Remove(id)
		log.Printf("rules sync: removed alert %s", id)
		return
	}
	s.index.Upsert(alert)
	log.Printf("rules sync: reload alert %s (%s, %d triggers)", id, alert.Symbol, len(alert.Triggers))
}

// Run blocks until ctx is cancelled.
func (s *Sync) Run(ctx context.Context) {
	listener := pq.NewListener(s.dsn, 2*time.Second, time.Minute, func(ev pq.ListenerEventType, err error) {
		if err != nil {
			log.Printf("rules sync: listener event=%d err=%v", ev, err)
		}
	})
	defer listener.Close()

	if err := listener.Listen(notifyChannel); err != nil {
		log.Printf("rules sync: LISTEN %s failed: %v", notifyChannel, err)
	}

	ticker := time.NewTicker(FullReloadInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case n := <-listener.Notify:
			// pq sends nil after a reconnect: anything could have changed meanwhile.
			if n == nil {
				if err := s.FullReload(ctx); err != nil {
					log.Printf("rules sync: full reload after reconnect failed: %v", err)
				}
				continue
			}
			s.reloadOne(ctx, n.Extra)
		case <-ticker.C:
			if err := s.FullReload(ctx); err != nil {
				log.Printf("rules sync: periodic full reload failed: %v", err)
			}
		}
	}
}
