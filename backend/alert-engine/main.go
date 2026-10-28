// alert-engine evaluates user alerts against live ticks and notifies on fire.
//
//	raw_data_trade ──▶ engine (rules + indicators in RAM) ──▶ alert_history + alert_triggered
//	alert_triggered ──▶ notifier ──▶ Telegram / email_requests (sent by mail-service)
//	Postgres LISTEN alert_changed ──▶ rules sync (keeps the in-memory rules fresh)
package main

import (
	"alert-engine/engine"
	"alert-engine/kafkax"
	"alert-engine/notify"
	"alert-engine/outbox"
	"alert-engine/rules"
	"context"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"

	"github.com/jmoiron/sqlx"
	"github.com/joho/godotenv"
	_ "github.com/lib/pq"
)

func main() {
	if err := godotenv.Load(".env"); err != nil {
		log.Printf("no .env file, using environment: %v", err)
	}
	cfg := LoadConfig()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	db, err := sqlx.Connect("postgres", cfg.PostgresDSN)
	if err != nil {
		log.Fatalf("connect postgres: %v", err)
	}
	defer db.Close()

	// Rules must be in memory before the first tick is evaluated.
	index := rules.NewIndex()
	ruleSync := rules.NewSync(rules.NewRepo(db), index, cfg.PostgresDSN)
	if err := ruleSync.FullReload(ctx); err != nil {
		log.Fatalf("load alerts: %v", err)
	}

	writer := kafkax.NewWriter(cfg.KafkaBrokers, cfg.TriggeredTopic)
	defer writer.Close()
	emailWriter := kafkax.NewWriter(cfg.KafkaBrokers, cfg.EmailTopic)
	defer emailWriter.Close()

	eng := engine.New(index, db, writer)
	notifier := notify.NewNotifier(db,
		notify.NewTelegram(cfg.TelegramBotToken),
		notify.NewEmail(emailWriter),
	)

	var wg sync.WaitGroup
	run := func(name string, fn func()) {
		wg.Add(1)
		go func() {
			defer wg.Done()
			fn()
			log.Printf("%s stopped", name)
		}()
	}

	run("rules sync", func() { ruleSync.Run(ctx) })
	run("outbox sweeper", func() { outbox.NewSweeper(db, writer).Run(ctx) })
	run("tick listener", func() {
		// No retries: HandleTick never fails a message (see its doc).
		err := kafkax.Listen(ctx, kafkax.ListenerConfig{
			Brokers: cfg.KafkaBrokers, Topic: cfg.TickTopic, GroupID: cfg.TickGroupID,
		}, eng.HandleTick)
		if err != nil {
			log.Printf("tick listener: %v", err)
			stop()
		}
	})
	run("notifier", func() {
		err := kafkax.Listen(ctx, kafkax.ListenerConfig{
			Brokers: cfg.KafkaBrokers, Topic: cfg.TriggeredTopic, GroupID: cfg.NotifierGroupID,
			MaxRetries: 5,
		}, notifier.Handle)
		if err != nil {
			log.Printf("notifier: %v", err)
			stop()
		}
	})

	log.Printf("alert-engine started: %d active alerts", index.Len())
	<-ctx.Done()
	log.Printf("alert-engine shutting down")
	wg.Wait()
}
