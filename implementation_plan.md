# Implementation Plan

## [Overview]
Add **AND/OR logic** between multiple trigger conditions in a user-defined alert, using a **single-level / single shared operator** model (one `logic` value for the whole condition list). Scope is **alert definition only** (schema + API + UI) — the evaluation/trigger engine is out of scope.

Today all conditions are stored flat in `triggeralert` with **no column expressing the logical operator**, so the system cannot represent or display whether all conditions must be true (AND) or only one (OR). Approach: add a `logic` column (`'AND' | 'OR'`, default `'AND'`) on `alert`; backend accepts/stores/returns `logic` with the trigger list; frontend adds an AND/OR toggle and supports adding/removing multiple conditions. Also fix three pre-existing bugs that block the feature: `triggeralert.condition varchar(1)` cannot hold `>=/<=/==`, `DeleteAlert` reads the wrong param name (`id` vs `alert_id`), and the `triggeralert → alert` FK has no `ON DELETE CASCADE` (so alerts with triggers cannot be deleted).

**On "execution order with multiple condition layers":** with one shared operator and one level, AND (and OR) are **associative**, so condition order does **not** change the result — no precedence/parentheses needed. A `position` column is added only for **stable display order**. Future nesting can migrate to DNF/JSONB without breaking the current API contract.

## [Types]

### Go DTO — `InteractionApp/internal/dto/Alert.go`
```go
package dto

const (
	LogicAnd = "AND"
	LogicOr  = "OR"
)

type Trigger struct {
	Indicator string   `json:"indicator" db:"indicator"`
	Operator  string   `json:"operator" db:"condition"`
	Threshold *float64 `json:"threshold" db:"value"`
	Position  int      `json:"position" db:"position"`
}

type AlertBase struct {
	Symbol string `json:"symbol" db:"symbol"`
	Active bool   `json:"active" db:"status" default:"true"`
	Logic  string `json:"logic" db:"logic"` // "AND" | "OR"
}

type AlertDetail struct {
	AlertBase
	ID        string    `json:"id" db:"id"`
	CreatedAt string    `json:"created_at" db:"created_at"`
	UpdatedAt string    `json:"updated_at" db:"updated_at"`
	Triggers  []Trigger `json:"triggers" db:"-"`
}

type AlertCreate struct {
	AlertBase
	Triggers *[]Trigger `json:"triggers" db:"-"`
}

type AlertUpdate struct {
	ID       string     `json:"id" db:"id"`
	Active   *bool      `json:"active" db:"status"`
	Logic    *string    `json:"logic" db:"logic"`
	Triggers *[]Trigger `json:"triggers" db:"-"`
}
```

### TypeScript — `FE/kstockFE/src/types/index.ts`
```ts
export type AlertLogic = 'AND' | 'OR'

export interface Trigger {
  indicator: string
  operator?: string
  condition?: string
  threshold: number | null
  position?: number
}

export interface AlertCreate {
  symbol: string
  active: boolean
  logic: AlertLogic
  triggers: Trigger[]
}

export interface AlertUpdate {
  id: string
  active?: boolean
  logic?: AlertLogic
  triggers?: Trigger[]
}

export interface AlertDetail {
  id: number | string
  symbol: string
  active?: boolean
  status?: boolean
  logic?: AlertLogic
  created_at: string
  updated_at: string
  triggers: Trigger[]
}
```

### DB
- `alert.logic varchar(3) not null default 'AND' check (logic in ('AND','OR'))`
- `triggeralert.condition varchar(4)` (from `varchar(1)`)
- `triggeralert.position int not null default 0`
- FK `triggeralert.alert_id → alert(id) on delete cascade`

## [Files]
New:
- `InteractionApp/docs/public/migrations/20260110_alert_logic_and_fixes.sql`

Modified (backend): `internal/dto/Alert.go`, `internal/handle/AlertHandle.go`, `internal/api/AlertRoute.go`, `internal/handle/handlers_test.go`.
Modified (schema dumps): `docs/public/alert.sql`, `docs/public/triggeralert.sql`.
Modified (docs): `docs/swagger.yaml` (`docs/docs.go` is swag-generated / stub — do not hand-edit).
Modified (frontend): `src/types/index.ts`, `src/services/alert.service.ts`, `src/pages/AlertsPage.tsx`, `src/pages/AlertsPage.css`.

## [Functions]
- `AlertHandle.go`: `normalizeLogic`, `validateTriggers` (new helpers); `CreateAlert` (validate + tx + position + logic), `GetAlertsBySymbol` (add logic, return array), `DeleteAlert` (fix param + tx), `UpdateAlert` (new).
- `AlertRoute.go`: register `PUT /:alert_id`.
- FE service: `createAlert` (send logic), `updateAlert` (new), `getAlertsBySymbol` (returns `AlertDetail[]`).
- FE page: `addTrigger`, `removeTrigger`, `updateTrigger`, `buildTriggers`; update `handleCreateAlert`, `handleEditAlert`.

## [Classes]
None (Go structs / React function components only).

## [Dependencies]
No new dependencies.

## [Testing]
- Go: extend `handlers_test.go` with sqlmock tests for logic validation, create with N triggers + position, get-as-array, update replace triggers, delete param.
- FE: `npm run build` + `npm run lint` (no unit-test framework configured).

## [Implementation Order]
1. Migration SQL + reference dumps
2. Go DTO
3. Helper functions
4. CreateAlert
5. GetAlertsBySymbol
6. UpdateAlert + route
7. DeleteAlert fix
8. Swagger
9. FE types
10. FE service
11. FE UI + CSS
12. Tests + build/lint
