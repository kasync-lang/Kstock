package engine

import (
	"alert-engine/indicator"
	"alert-engine/model"
	"testing"
)

// stateAfter feeds prices for one symbol and returns its final state.
func stateAfter(prices ...float64) *indicator.SymbolState {
	store := indicator.NewStore()
	var s *indicator.SymbolState
	for i, p := range prices {
		s = store.Apply(model.Tick{S: "AAPL", P: p, T: int64(i)})
	}
	return s
}

func price(op string, thr float64) model.Trigger {
	return model.Trigger{Indicator: model.IndicatorPrice, Operator: op, Threshold: thr}
}

func TestEval(t *testing.T) {
	tests := []struct {
		name     string
		logic    string
		triggers []model.Trigger
		prices   []float64
		want     bool
	}{
		{"gt true", model.LogicAnd, []model.Trigger{price(">", 150)}, []float64{151}, true},
		{"gt false at threshold", model.LogicAnd, []model.Trigger{price(">", 150)}, []float64{150}, false},
		{"gte at threshold", model.LogicAnd, []model.Trigger{price(">=", 150)}, []float64{150}, true},
		{"lt true", model.LogicAnd, []model.Trigger{price("<", 150)}, []float64{149.9}, true},
		{"lte false", model.LogicAnd, []model.Trigger{price("<=", 150)}, []float64{150.1}, false},
		{"neq true", model.LogicAnd, []model.Trigger{price("!=", 150)}, []float64{150.1}, true},
		{"eq exact", model.LogicAnd, []model.Trigger{price("==", 150)}, []float64{150}, true},
		{"eq crossed up", model.LogicAnd, []model.Trigger{price("==", 150)}, []float64{149.5, 150.5}, true},
		{"eq crossed down", model.LogicAnd, []model.Trigger{price("==", 150)}, []float64{150.5, 149.5}, true},
		{"eq no cross", model.LogicAnd, []model.Trigger{price("==", 150)}, []float64{151, 152}, false},
		{"eq first tick no prev", model.LogicAnd, []model.Trigger{price("==", 150)}, []float64{151}, false},
		{"and both true", model.LogicAnd, []model.Trigger{price(">", 100), price("<", 200)}, []float64{150}, true},
		{"and one false", model.LogicAnd, []model.Trigger{price(">", 100), price("<", 120)}, []float64{150}, false},
		{"or one true", model.LogicOr, []model.Trigger{price("<", 100), price(">", 120)}, []float64{150}, true},
		{"or none true", model.LogicOr, []model.Trigger{price("<", 100), price(">", 200)}, []float64{150}, false},
		{"unknown operator", model.LogicAnd, []model.Trigger{price("~", 150)}, []float64{151}, false},
		{"indicator without value", model.LogicAnd, []model.Trigger{{Indicator: model.IndicatorRSI, Operator: ">", Threshold: 70}}, []float64{151}, false},
		{"or skips missing indicator", model.LogicOr, []model.Trigger{{Indicator: model.IndicatorRSI, Operator: ">", Threshold: 70}, price(">", 150)}, []float64{151}, true},
		{"no triggers", model.LogicAnd, nil, []float64{151}, false},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			alert := &model.Alert{ID: "a1", Symbol: "AAPL", Logic: tc.logic, Triggers: tc.triggers}
			if got := Eval(alert, stateAfter(tc.prices...)); got != tc.want {
				t.Errorf("Eval() = %v, want %v", got, tc.want)
			}
		})
	}
}

// TODO(you): khi làm xong VOLUME/RSI, thêm case ở đây (vd. VOLUME reset khi sang ngày,
// RSI chưa đủ 14 nến -> false).
