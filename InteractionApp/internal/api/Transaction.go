package api

import (
	"Kstock/internal/handle"

	"github.com/gin-gonic/gin"
)

func RegisterTransactionHandle(router *gin.RouterGroup) {
	transactionGroup := router.Group("/transactions")
	{
		transactionGroup.POST("/", handle.TransactionHandle)
		transactionGroup.GET("/history", handle.TransactionHistoryHandle)
	}

}
