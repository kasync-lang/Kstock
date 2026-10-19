package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

// validOperators is the set of comparison operators accepted for a trigger.
var validOperators = map[string]struct{}{
	">":  {},
	"<":  {},
	">=": {},
	"<=": {},
	"==": {},
	"!=": {},
}

// normalizeLogic uppercases and validates the alert-level boolean operator.
// An empty value defaults to AND. The bool result reports validity: false means
// the caller supplied an unknown operator.
func normalizeLogic(raw string) (string, bool) {
	switch strings.ToUpper(strings.TrimSpace(raw)) {
	case "", dto.LogicAnd:
		return dto.LogicAnd, true
	case dto.LogicOr:
		return dto.LogicOr, true
	default:
		return "", false
	}
}

// validateTriggers ensures at least one well-formed condition is supplied.
func validateTriggers(triggers []dto.Trigger) error {
	if len(triggers) == 0 {
		return errors.New("at least one trigger is required")
	}
	for i, t := range triggers {
		if strings.TrimSpace(t.Indicator) == "" {
			return fmt.Errorf("trigger %d: indicator is required", i)
		}
		if _, ok := validOperators[t.Operator]; !ok {
			return fmt.Errorf("trigger %d: invalid operator %q", i, t.Operator)
		}
		if t.Threshold == nil {
			return fmt.Errorf("trigger %d: threshold is required", i)
		}
	}
	return nil
}

func CreateAlert(c *gin.Context) {
	// Implementation for creating an alert
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	var data_create dto.AlertCreate
	err2 := c.ShouldBind(&data_create)
	if err2 != nil {
		c.JSON(400, gin.H{"error": err2.Error()})
		c.Abort()
		return
	}
	if data_create.Triggers == nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "triggers is required"})
		c.Abort()
		return
	}
	if err := validateTriggers(*data_create.Triggers); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		c.Abort()
		return
	}
	logic, ok := normalizeLogic(data_create.Logic)
	if !ok {
		c.JSON(http.StatusBadRequest, gin.H{"error": "logic must be AND or OR"})
		c.Abort()
		return
	}
	db := server.GetDB()
	tx, err := db.Beginx()
	if err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error starting create-alert transaction: %v", err)
		c.Abort()
		return
	}
	defer tx.Rollback()

	query_create_alert := `insert into alert (user_id, symbol, status, logic) values ($1, $2, $3, $4) returning id`
	var alert_id string
	err3 := tx.Get(&alert_id, query_create_alert, sub, data_create.Symbol, data_create.Active, logic)
	if err3 != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error creating alert: %v", err3)
		c.Abort()
		return
	}
	for idx, trigger := range *data_create.Triggers {
		query_create_trigger := `insert into triggeralert (alert_id, indicator, condition, value, position) values ($1, $2, $3, $4, $5)`
		_, err4 := tx.Exec(query_create_trigger, alert_id, trigger.Indicator, trigger.Operator, trigger.Threshold, idx)
		if err4 != nil {
			c.JSON(500, gin.H{"error": "Internal Server Error"})
			log.Println(err4.Error())
			c.Abort()
			return
		}
	}
	if err := tx.Commit(); err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error committing create-alert transaction: %v", err)
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"id": alert_id})
}
func GetAlertsBySymbol(c *gin.Context) {
	// Implementation for getting alerts
	symbol := c.Param("symbol")
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	db := server.GetDB()

	query2 := `SELECT json_build_object(
               'id', a.id,
               'symbol', a.symbol,
               'status', a.status,
               'logic', a.logic,
               'created_at', a.created_at,
               'updated_at', a.updated_at,
               'triggers', COALESCE(t.triggers, '[]'::json)
       )
FROM alert a
         LEFT JOIN LATERAL (
    SELECT json_agg(
                   json_build_object(
                           'indicator', o.indicator,
                           'threshold', o.value,
                           'condition', o.condition,
                           'operator', o.condition,
                           'position', o.position
                   ) ORDER BY o.position
           ) AS triggers
    FROM triggeralert o
    WHERE o.alert_id = a.id
    ) t ON true
WHERE a.symbol = $1 AND a.user_id = $2
ORDER BY a.created_at;`
	rows := []json.RawMessage{}
	row, err := db.Query(query2, symbol, sub)
	if err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		c.Abort()
		return
	}
	defer row.Close()
	for row.Next() {
		var raw json.RawMessage
		if err := row.Scan(&raw); err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			c.Abort()
			return
		}
		rows = append(rows, raw)
	}
	if err := row.Err(); err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		c.Abort()
		return
	}

	c.JSON(200, gin.H{"data": rows})

}
func DeleteAlert(c *gin.Context) {
	// Implementation for deleting an alert
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	alert_id := c.Param("alert_id")
	db := server.GetDB()
	tx, err := db.Beginx()
	if err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error starting delete-alert transaction: %v", err)
		c.Abort()
		return
	}
	defer tx.Rollback()

	// Remove child triggers first so the delete works even on databases where the
	// foreign key has not yet been migrated to ON DELETE CASCADE.
	query_delete_triggers := `delete from triggeralert where alert_id = $1 and exists (select 1 from alert where id = $1 and user_id = $2)`
	if _, err := tx.Exec(query_delete_triggers, alert_id, sub); err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error deleting alert triggers: %v", err)
		c.Abort()
		return
	}
	query_delete_alert := `delete from alert where id = $1 and user_id = $2`
	if _, err := tx.Exec(query_delete_alert, alert_id, sub); err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error deleting alert: %v", err)
		c.Abort()
		return
	}
	if err := tx.Commit(); err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error committing delete-alert transaction: %v", err)
		c.Abort()
		return
	}
	c.JSON(http.StatusNoContent, gin.H{"message": "Alert deleted successfully"})
}

// UpdateAlert replaces the mutable parts of an alert (active flag, AND/OR logic
// and/or the full set of trigger conditions). Ownership is enforced by user_id.
func UpdateAlert(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	alert_id := c.Param("alert_id")
	var data_update dto.AlertUpdate
	if err := c.ShouldBind(&data_update); err != nil {
		c.JSON(400, gin.H{"error": err.Error()})
		c.Abort()
		return
	}
	var logic *string
	if data_update.Logic != nil {
		normalized, ok := normalizeLogic(*data_update.Logic)
		if !ok {
			c.JSON(http.StatusBadRequest, gin.H{"error": "logic must be AND or OR"})
			c.Abort()
			return
		}
		logic = &normalized
	}
	if data_update.Triggers != nil {
		if err := validateTriggers(*data_update.Triggers); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			c.Abort()
			return
		}
	}
	db := server.GetDB()
	tx, err := db.Beginx()
	if err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error starting update-alert transaction: %v", err)
		c.Abort()
		return
	}
	defer tx.Rollback()

	query_update_alert := `update alert
set logic = coalesce($1, logic),
    status = coalesce($2, status),
    updated_at = now()
where id = $3 and user_id = $4`
	res, err := tx.Exec(query_update_alert, logic, data_update.Active, alert_id, sub)
	if err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error updating alert: %v", err)
		c.Abort()
		return
	}
	affected, err := res.RowsAffected()
	if err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		c.Abort()
		return
	}
	if affected == 0 {
		c.JSON(http.StatusNotFound, gin.H{"error": "alert not found"})
		c.Abort()
		return
	}
	if data_update.Triggers != nil {
		query_delete_triggers := `delete from triggeralert where alert_id = $1`
		if _, err := tx.Exec(query_delete_triggers, alert_id); err != nil {
			c.JSON(500, gin.H{"error": "Internal Server Error"})
			log.Printf("Error clearing alert triggers: %v", err)
			c.Abort()
			return
		}
		query_insert_trigger := `insert into triggeralert (alert_id, indicator, condition, value, position) values ($1, $2, $3, $4, $5)`
		for idx, trigger := range *data_update.Triggers {
			if _, err := tx.Exec(query_insert_trigger, alert_id, trigger.Indicator, trigger.Operator, trigger.Threshold, idx); err != nil {
				c.JSON(500, gin.H{"error": "Internal Server Error"})
				log.Printf("Error updating alert trigger: %v", err)
				c.Abort()
				return
			}
		}
	}
	if err := tx.Commit(); err != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error committing update-alert transaction: %v", err)
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"data": gin.H{"id": alert_id}})
}

