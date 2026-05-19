package main

import (
	"Kstock/internal/api"
	"Kstock/internal/config"
	"Kstock/internal/dto"
	"Kstock/internal/middleware"
	"Kstock/internal/server"
	"context"
	"errors"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"golang.org/x/sync/errgroup"
)

func main() {
	// Init: load env/config, jwt keystore, db ...

	// Cancel both Kafka listener and HTTP server on Ctrl+C (SIGINT) or Docker stop (SIGTERM).
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	server.StartServer(ctx)
	cfgKafka := server.NewKafkaListenerConfigFromConfig(config.Cfg)
	priceStore := dto.NewPriceStore()
	// Add usd
	priceStore.Update("USD", 1.0)

	// Gin router
	r := gin.Default()
	// Inject PriceStore
	r.Use(middleware.InjectPriceStore(priceStore))
	api.RegisterAllRoutes(r)

	addr := ":8080"
	if config.Cfg != nil && config.Cfg.APPPort != "" {
		addr = ":" + config.Cfg.APPPort
	}

	httpSrv := &http.Server{
		Addr:    addr,
		Handler: r,
	}

	g, gctx := errgroup.WithContext(ctx)

	// Kafka consumer loop
	g.Go(func() error {
		return server.EventKafkaListener(gctx, cfgKafka, server.NewPriceHandler(priceStore))
	})

	// HTTP server
	g.Go(func() error {
		log.Printf("http: listening on %s", addr)
		err := httpSrv.ListenAndServe()
		if err == nil || errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	})

	// Optional: log current in-memory prices periodically (does not block shutdown)
	//g.Go(func() error {
	//	t := time.NewTicker(10 * time.Second)
	//	defer t.Stop()
	//	for {
	//		select {
	//		case <-gctx.Done():
	//			return nil
	//		case <-t.C:
	//			for symbol, price := range priceStore.GetAll() {
	//				log.Printf("price: %s - %v", symbol, price)
	//			}
	//		}
	//	}
	//})

	// When context is canceled, gracefully shutdown HTTP server.
	g.Go(func() error {
		<-gctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		return httpSrv.Shutdown(shutdownCtx)
	})

	if err := g.Wait(); err != nil {
		log.Fatal(err)
	}
}
