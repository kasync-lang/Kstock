package rules

import (
	"alert-engine/model"
	"testing"
)

func TestIndex(t *testing.T) {
	idx := NewIndex()
	idx.ReplaceAll([]*model.Alert{
		{ID: "a1", Symbol: "AAPL"},
		{ID: "a2", Symbol: "AAPL"},
		{ID: "m1", Symbol: "MSFT"},
	})
	if got := len(idx.ForSymbol("AAPL")); got != 2 {
		t.Fatalf("AAPL alerts = %d, want 2", got)
	}

	idx.Remove("a1")
	if got := len(idx.ForSymbol("AAPL")); got != 1 {
		t.Fatalf("after remove AAPL alerts = %d, want 1", got)
	}

	// Upsert under a new symbol moves the alert.
	idx.Upsert(&model.Alert{ID: "a2", Symbol: "TSLA"})
	if got := len(idx.ForSymbol("AAPL")); got != 0 {
		t.Fatalf("after move AAPL alerts = %d, want 0", got)
	}
	if got := len(idx.ForSymbol("TSLA")); got != 1 {
		t.Fatalf("after move TSLA alerts = %d, want 1", got)
	}
	if got := idx.Len(); got != 2 {
		t.Fatalf("Len = %d, want 2", got)
	}
}
