package dto

import (
	"fmt"
	"sync"
)

type PriceStore struct {
	data map[string]float64
	mux  sync.RWMutex
}
type Tick struct {
	C []string `json:"c"`
	P float64  `json:"p"`
	S string   `json:"s"`
	T int64    `json:"t"`
	V int      `json:"v"`
}

// Print all field
func (t *Tick) String() string {
	return "Tick{C: " + fmt.Sprintf("%v", t.C) + ", P: " + fmt.Sprintf("%v", t.P) + ", S: " + fmt.Sprintf("%v", t.S) + ", T: " + fmt.Sprintf("%v", t.T) + ", V: " + fmt.Sprintf("%v", t.V) + "}"
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
func (s *PriceStore) GetAll() map[string]float64 {
	s.mux.RLock()
	defer s.mux.RUnlock()
	prices := make(map[string]float64, len(s.data))
	for symbol, price := range s.data {
		prices[symbol] = price
	}
	return prices
}
