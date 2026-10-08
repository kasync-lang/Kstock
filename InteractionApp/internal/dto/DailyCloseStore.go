package dto

import "sync"

// DailyClose holds the two most recent daily closes of a symbol (from ohlcv_1d).
// Last is the close of the latest daily candle, Prev is the close of the candle before it.
type DailyClose struct {
	Last    float64
	Prev    float64
	HasLast bool
	HasPrev bool
}

// DailyCloseStore is an in-memory, concurrency-safe cache of DailyClose per symbol.
// It is refreshed periodically in the background so request handlers never hit ClickHouse.
type DailyCloseStore struct {
	mux  sync.RWMutex
	data map[string]DailyClose
}

func NewDailyCloseStore() *DailyCloseStore {
	return &DailyCloseStore{data: make(map[string]DailyClose)}
}

func (s *DailyCloseStore) Get(symbol string) (DailyClose, bool) {
	s.mux.RLock()
	defer s.mux.RUnlock()
	v, ok := s.data[symbol]
	return v, ok
}

// ReplaceAll atomically swaps the whole cache content.
func (s *DailyCloseStore) ReplaceAll(data map[string]DailyClose) {
	if data == nil {
		data = make(map[string]DailyClose)
	}
	s.mux.Lock()
	s.data = data
	s.mux.Unlock()
}

func (s *DailyCloseStore) Len() int {
	s.mux.RLock()
	defer s.mux.RUnlock()
	return len(s.data)
}

