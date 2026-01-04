package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"encoding/json"
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

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
	db := server.GetDB()
	symbol := data_create.Symbol
	is_active := data_create.Active
	query_create_alert := `insert into alert (user_id, symbol, status) values ($1, $2, $3) returning id`
	var alert_id string
	err3 := db.Get(&alert_id, query_create_alert, sub, symbol, is_active)
	var triggers = data_create.Triggers
	if err3 != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error" + err3.Error()})
		c.Abort()
		return
	}
	for _, trigger := range *triggers {
		query_create_trigger := `insert into triggeralert (alert_id, indicator, condition, value) values ($1, $2, $3, $4)`
		_, err4 := db.Exec(query_create_trigger, alert_id, trigger.Indicator, trigger.Operator, trigger.Threshold)
		if err4 != nil {
			c.JSON(500, gin.H{"error": "Internal Server Error"})
			log.Println(err.Error())
			c.Abort()
			return
		}
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

	query_get_alerts := `select alert.id from alert where user_id = $1 and symbol = $2`
	var alert_id []string
	db.Select(&alert_id, query_get_alerts, sub, symbol)
	query2 := `SELECT json_build_object(
               'id', a.id,
               'symbol', a.symbol,
               'status', a.status,
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
                           'condition', o.condition
                   )
           ) AS triggers
    FROM triggeralert o
    WHERE o.alert_id = a.id
    ) t ON true
WHERE a.symbol = $1 AND a.user_id = $2;`
	var raw json.RawMessage
	row, err := db.Query(query2, symbol, sub)
	if err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		c.Abort()
		return
	}
	for row.Next() {
		err := row.Scan(&raw)
		if err != nil {
			c.JSON(500, gin.H{"error": err.Error()})
			c.Abort()
			return
		}
	}
	if err != nil {
		c.JSON(500, gin.H{"error": err.Error()})
		c.Abort()
		return
	}

	c.JSON(200, gin.H{"data": raw})

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
	query := `delete from alert where id = $1 and user_id = $2`
	alert_id := c.Param("id")
	db := server.GetDB()
	_, err2 := db.Exec(query, alert_id, sub)
	if err2 != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error" + err2.Error()})
		c.Abort()
		return
	}
	c.JSON(http.StatusNoContent, gin.H{"message": "Alert deleted successfully"})
}
