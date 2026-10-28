// Package indicator keeps the per-symbol values that triggers compare against.
//
// State is only touched from the tick-handling goroutine (one kafka-go reader
// serves all assigned partitions sequentially), so it needs no locking. If you
// ever process partitions in parallel, shard Store by symbol instead of adding
// a global mutex.
package indicator

import "alert-engine/model"

// Reading is the current value of one indicator plus the value before the last
// update; Prev is what lets "==" mean "crossed the threshold".
type Reading struct {
	Cur     float64
	Prev    float64
	HasPrev bool
}

type SymbolState struct {
	readings map[string]*Reading

	// TODO(you): VOLUME — cumulative volume of the current trading day.
	//   dayVolume float64
	//   day       string // "2006-01-02" in America/New_York, from tick.T (unix ms)
	// Reset dayVolume when the day changes, then s.set(model.IndicatorVolume, dayVolume).

	// TODO(you): RSI — see rsi.go.
	//   rsi *RSI
}

func newSymbolState() *SymbolState {
	return &SymbolState{readings: make(map[string]*Reading)}
}

func (s *SymbolState) set(indicator string, value float64) {
	r, ok := s.readings[indicator]
	if !ok {
		s.readings[indicator] = &Reading{Cur: value}
		return
	}
	r.Prev, r.HasPrev = r.Cur, true
	r.Cur = value
}

// OnTick folds one trade into every indicator of the symbol.
func (s *SymbolState) OnTick(t model.Tick) {
	s.set(model.IndicatorPrice, t.P)

	// TODO(you): update VOLUME and RSI here.
}

// Value returns the reading for an indicator, or false when it has no value yet
// (e.g. RSI still warming up). Triggers on a missing value evaluate to false.
func (s *SymbolState) Value(indicator string) (Reading, bool) {
	r, ok := s.readings[indicator]
	if !ok {
		return Reading{}, false
	}
	return *r, true
}

type Store struct {
	symbols map[string]*SymbolState
}

func NewStore() *Store {
	return &Store{symbols: make(map[string]*SymbolState)}
}

// Apply updates the symbol's indicators with a tick and returns its state.
func (st *Store) Apply(t model.Tick) *SymbolState {
	s, ok := st.symbols[t.S]
	if !ok {
		s = newSymbolState()
		st.symbols[t.S] = s
	}
	s.OnTick(t)
	return s
}
