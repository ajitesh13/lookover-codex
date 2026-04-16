package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ajitesh/lookover-codex/backend/internal/api"
	"github.com/ajitesh/lookover-codex/backend/internal/config"
	"github.com/ajitesh/lookover-codex/backend/internal/controls"
	"github.com/ajitesh/lookover-codex/backend/internal/demo"
	"github.com/ajitesh/lookover-codex/backend/internal/evaluator"
	"github.com/ajitesh/lookover-codex/backend/internal/store"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	db, err := store.New(cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("connect store: %v", err)
	}
	defer db.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	if err = db.Migrate(ctx); err != nil {
		log.Fatalf("migrate schema: %v", err)
	}

	manifests, err := controls.LoadAll(cfg.ControlsDir)
	if err != nil {
		log.Fatalf("load control manifests: %v", err)
	}
	for _, manifest := range manifests {
		if err = db.UpsertPolicyVersion(ctx, manifest); err != nil {
			log.Fatalf("seed policy version: %v", err)
		}
	}

	engine := evaluator.New(manifests)
	if err = db.SeedUser(ctx, cfg.SeedReviewerEmail, cfg.SeedReviewerPassword); err != nil {
		log.Fatalf("seed reviewer user: %v", err)
	}
	if err = demo.Seed(ctx, db, engine, cfg.ReportsDir); err != nil {
		log.Fatalf("seed demo data: %v", err)
	}

	server := &http.Server{
		Addr:              ":" + cfg.APIPort,
		Handler:           api.New(db, engine, cfg.ReportsDir),
		ReadHeaderTimeout: 5 * time.Second,
	}

	go func() {
		log.Printf("compliance engine listening on :%s", cfg.APIPort)
		if serveErr := server.ListenAndServe(); serveErr != nil && serveErr != http.ErrServerClosed {
			log.Fatalf("listen and serve: %v", serveErr)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()
	if err = server.Shutdown(shutdownCtx); err != nil {
		log.Printf("shutdown error: %v", err)
	}
}
