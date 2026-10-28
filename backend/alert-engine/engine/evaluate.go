package engine

import (
	"alert-engine/indicator"
	"alert-engine/model"
)

// Eval reports whether the alert's triggers hold for the symbol's current state.
// Logic AND needs every trigger true, OR needs one; an unknown logic is treated
// as AND, matching core-api's default.
func Eval(a *model.Alert, s *indicator.SymbolState) bool {
	if len(a.Triggers) == 0 {
		return false
	}
	or := a.Logic == model.LogicOr
	for _, t := range a.Triggers {
		ok := evalTrigger(t, s)
		if or && ok {
			return true
		}
		if !or && !ok {
			return false
		}
	}
	return !or
}

func evalTrigger(t model.Trigger, s *indicator.SymbolState) bool {
	r, ok := s.Value(t.Indicator)
	if !ok {
		return false
	}
	return compare(t.Operator, r, t.Threshold)
}

func compare(op string, r indicator.Reading, thr float64) bool {
	cur := r.Cur
	switch op {
	case ">":
		return cur > thr
	case "<":
		return cur < thr
	case ">=":
		return cur >= thr
	case "<=":
		return cur <= thr
	case "!=":
		return cur != thr
	case "==":
		// Prices are floats and trade in jumps, so exact equality almost never
		// happens. "==" fires when the value lands on or crosses the threshold.
		if cur == thr {
			return true
		}
		if !r.HasPrev {
			return false
		}
		return (r.Prev < thr && cur > thr) || (r.Prev > thr && cur < thr)
	default:
		return false
	}
}
