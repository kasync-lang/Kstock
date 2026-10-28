package rules

import (
	"alert-engine/model"
	"context"

	"github.com/jmoiron/sqlx"
)

type Repo struct {
	db *sqlx.DB
}

func NewRepo(db *sqlx.DB) *Repo {
	return &Repo{db: db}
}

type alertRow struct {
	ID        string  `db:"id"`
	UserID    string  `db:"user_id"`
	Symbol    string  `db:"symbol"`
	Logic     string  `db:"logic"`
	Indicator string  `db:"indicator"`
	Operator  string  `db:"condition"`
	Threshold float64 `db:"value"`
	Position  int     `db:"position"`
}

// Only active alerts with fully-formed triggers are loaded; an alert without
// triggers can never fire, so the inner join drops it on purpose.
const selectActive = `select a.id, a.user_id, a.symbol, a.logic,
       t.indicator, t.condition, t.value, t.position
from alert a
         join triggeralert t on t.alert_id = a.id
where a.status = true
  and t.indicator is not null
  and t.condition is not null
  and t.value is not null`

// LoadActive returns every active alert. Used at startup and for the periodic
// full reload.
func (r *Repo) LoadActive(ctx context.Context) ([]*model.Alert, error) {
	var rows []alertRow
	if err := r.db.SelectContext(ctx, &rows, selectActive+` order by a.id, t.position`); err != nil {
		return nil, err
	}
	return groupRows(rows), nil
}

// LoadOne returns the alert if it is still active, or nil when it was deleted
// or switched off.
func (r *Repo) LoadOne(ctx context.Context, id string) (*model.Alert, error) {
	var rows []alertRow
	if err := r.db.SelectContext(ctx, &rows, selectActive+` and a.id = $1 order by t.position`, id); err != nil {
		return nil, err
	}
	alerts := groupRows(rows)
	if len(alerts) == 0 {
		return nil, nil
	}
	return alerts[0], nil
}

// groupRows folds the alert x trigger join back into one Alert per id. Rows must
// be ordered by alert id.
func groupRows(rows []alertRow) []*model.Alert {
	var alerts []*model.Alert
	var cur *model.Alert
	for _, row := range rows {
		if cur == nil || cur.ID != row.ID {
			cur = &model.Alert{ID: row.ID, UserID: row.UserID, Symbol: row.Symbol, Logic: row.Logic}
			alerts = append(alerts, cur)
		}
		cur.Triggers = append(cur.Triggers, model.Trigger{
			Indicator: row.Indicator,
			Operator:  row.Operator,
			Threshold: row.Threshold,
			Position:  row.Position,
		})
	}
	return alerts
}
