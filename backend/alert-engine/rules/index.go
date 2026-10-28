package rules

import (
	"alert-engine/model"
	"sync"
)

// Index is the in-memory copy of active alerts, keyed by symbol so a tick only
// looks at the alerts of its own symbol. The tick loop reads it, the sync loop
// writes it, hence the RWMutex.
type Index struct {
	mux      sync.RWMutex
	bySymbol map[string]map[string]*model.Alert
	symbolOf map[string]string // alert id -> symbol, to remove without knowing the symbol
}

func NewIndex() *Index {
	return &Index{
		bySymbol: make(map[string]map[string]*model.Alert),
		symbolOf: make(map[string]string),
	}
}

// ReplaceAll swaps the whole index in one step (startup and periodic reload).
func (i *Index) ReplaceAll(alerts []*model.Alert) {
	bySymbol := make(map[string]map[string]*model.Alert)
	symbolOf := make(map[string]string, len(alerts))
	for _, a := range alerts {
		if bySymbol[a.Symbol] == nil {
			bySymbol[a.Symbol] = make(map[string]*model.Alert)
		}
		bySymbol[a.Symbol][a.ID] = a
		symbolOf[a.ID] = a.Symbol
	}

	i.mux.Lock()
	defer i.mux.Unlock()
	i.bySymbol = bySymbol
	i.symbolOf = symbolOf
}

func (i *Index) Upsert(a *model.Alert) {
	i.mux.Lock()
	defer i.mux.Unlock()
	i.removeLocked(a.ID)
	if i.bySymbol[a.Symbol] == nil {
		i.bySymbol[a.Symbol] = make(map[string]*model.Alert)
	}
	i.bySymbol[a.Symbol][a.ID] = a
	i.symbolOf[a.ID] = a.Symbol
}

func (i *Index) Remove(id string) {
	i.mux.Lock()
	defer i.mux.Unlock()
	i.removeLocked(id)
}

func (i *Index) removeLocked(id string) {
	symbol, ok := i.symbolOf[id]
	if !ok {
		return
	}
	delete(i.bySymbol[symbol], id)
	if len(i.bySymbol[symbol]) == 0 {
		delete(i.bySymbol, symbol)
	}
	delete(i.symbolOf, id)
}

// ForSymbol returns a snapshot slice, safe to iterate while the index changes.
func (i *Index) ForSymbol(symbol string) []*model.Alert {
	i.mux.RLock()
	defer i.mux.RUnlock()
	alerts := make([]*model.Alert, 0, len(i.bySymbol[symbol]))
	for _, a := range i.bySymbol[symbol] {
		alerts = append(alerts, a)
	}
	return alerts
}

func (i *Index) Len() int {
	i.mux.RLock()
	defer i.mux.RUnlock()
	return len(i.symbolOf)
}
