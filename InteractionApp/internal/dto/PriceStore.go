package dto

import (
	"sync"
	"time"
)

type PriceStore struct {
	data map[string]float64
	mux  sync.RWMutex
}
type Tick struct {
	C []int     `json:"c"`
	P float64   `json:"p"`
	S string    `json:"s"`
	T time.Time `json:"t"`
	V int       `json:"v"`
}

func (s *PriceStore) Get(symbol string) (float64, bool) {
	s.mux.RLock()
	defer s.mux.RUnlock()
	val, ok := s.data[symbol]
	return val, ok
}
func NewPriceStore() *PriceStore {
	return &PriceStore{
		data: make(map[string]float64),
	}
}
func (s *PriceStore) Update(symbol string, value float64) {
	s.mux.Lock()
	defer s.mux.Unlock()
	s.data[symbol] = value
}
