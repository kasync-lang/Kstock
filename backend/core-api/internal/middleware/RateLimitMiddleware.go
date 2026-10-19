package middleware

import (
	"net/http"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
)

type bucket struct {
	tokens     int
	lastRefill time.Time
}

func RateLimit(maxTokens int, refillInterval time.Duration) gin.HandlerFunc {
	var (
		mu      sync.Mutex
		buckets = make(map[string]*bucket)
	)

	return func(c *gin.Context) {
		ip := c.ClientIP()
		now := time.Now()

		mu.Lock()
		b, ok := buckets[ip]
		if !ok {
			b = &bucket{
				tokens:     maxTokens,
				lastRefill: now,
			}
			buckets[ip] = b
		}

		// refill
		if now.Sub(b.lastRefill) >= refillInterval {
			b.tokens = maxTokens
			b.lastRefill = now
		}

		if b.tokens <= 0 {
			mu.Unlock()
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
				"error": "rate limit exceeded",
			})
			return
		}

		b.tokens--
		mu.Unlock()

		c.Next()
	}
}
