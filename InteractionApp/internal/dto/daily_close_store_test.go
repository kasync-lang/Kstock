package dto

import (
	"sync"
	"testing"
)

func TestDailyCloseStoreOperations(t *testing.T) {
	store := NewDailyCloseStore()
	if store.Len() != 0 {
		t.Fatalf("expected empty store, got len %d", store.Len())
	}

	data := map[string]DailyClose{
		"AAPL": {Last: 150.0, Prev: 145.0, HasLast: true, HasPrev: true},
		"MSFT": {Last: 300.0, HasLast: true},
	}
	store.ReplaceAll(data)

	if store.Len() != 2 {
		t.Fatalf("expected len 2, got %d", store.Len())
	}

	aapl, ok := store.Get("AAPL")
	if !ok || aapl.Last != 150.0 || aapl.Prev != 145.0 || !aapl.HasLast || !aapl.HasPrev {
		t.Fatalf("unexpected AAPL: %+v, ok=%v", aapl, ok)
	}

	if _, ok := store.Get("NONEXISTENT"); ok {
		t.Fatal("expected ok=false for non-existent symbol")
	}

	// Replacing with nil should not panic and should reset to empty map
	store.ReplaceAll(nil)
	if store.Len() != 0 {
		t.Fatalf("expected len 0 after nil replace, got %d", store.Len())
	}
}

func TestDailyCloseStoreConcurrentAccess(t *testing.T) {
	store := NewDailyCloseStore()
	const workers = 32
	var wg sync.WaitGroup

	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			store.ReplaceAll(map[string]DailyClose{
				"AAPL": {Last: float64(idx), HasLast: true},
			})
			_, _ = store.Get("AAPL")
			_ = store.Len()
		}(i)
	}
	wg.Wait()
}

