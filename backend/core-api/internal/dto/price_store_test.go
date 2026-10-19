package dto

import (
	"sync"
	"testing"
)

func TestPriceStoreUpdateGetAndSnapshot(t *testing.T) {
	store := NewPriceStore()
	store.Update("AAPL", 123.45)

	price, ok := store.Get("AAPL")
	if !ok || price != 123.45 {
		t.Fatalf("Get(AAPL) = (%v, %v), want (123.45, true)", price, ok)
	}
	if _, ok := store.Get("MISSING"); ok {
		t.Fatal("Get(MISSING) unexpectedly found a price")
	}

	snapshot := store.GetAll()
	snapshot["AAPL"] = 0
	snapshot["MSFT"] = 1
	price, _ = store.Get("AAPL")
	if price != 123.45 {
		t.Fatalf("snapshot mutation changed stored price to %v", price)
	}
	if _, ok := store.Get("MSFT"); ok {
		t.Fatal("snapshot mutation added a stored symbol")
	}
}

func TestPriceStoreConcurrentAccess(t *testing.T) {
	store := NewPriceStore()
	const workers = 32
	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			store.Update("AAPL", float64(i))
			_, _ = store.Get("AAPL")
			_ = store.GetAll()
		}(i)
	}
	wg.Wait()
	if _, ok := store.Get("AAPL"); !ok {
		t.Fatal("concurrent updates did not retain AAPL")
	}
}

func TestTickString(t *testing.T) {
	tick := Tick{C: []string{"A"}, P: 1.5, S: "AAPL", T: 2, V: 3}
	want := "Tick{C: [A], P: 1.5, S: AAPL, T: 2, V: 3}"
	if got := tick.String(); got != want {
		t.Fatalf("String() = %q, want %q", got, want)
	}
}
