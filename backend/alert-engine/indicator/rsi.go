package indicator

// TODO(you): RSI(14) on 1-minute closes.
//
// Gợi ý cách làm (Wilder's smoothing):
//  1. Build nến 1m từ tick: bucket = tick.T / 60_000. Khi bucket đổi, nến cũ
//     đóng lại với close = giá tick cuối của nến đó -> gọi rsi.AddClose(close).
//  2. AddClose: change = close - prevClose; gain = max(change, 0); loss = max(-change, 0)
//     - 14 nến đầu: cộng dồn, sau đó avgGain = sum/14, avgLoss = sum/14
//     - sau đó: avgGain = (avgGain*13 + gain)/14, avgLoss tương tự
//     - RSI = 100 - 100/(1 + avgGain/avgLoss)   (avgLoss == 0 -> RSI = 100)
//  3. Chỉ s.set(model.IndicatorRSI, value) khi đã đủ 14 thay đổi (Ready()).
//  4. Warm-up lúc startup để không phải chờ 15 phút: query ClickHouse
//       SELECT symbol, close FROM aggregate_db.ohlcv_1m
//       WHERE symbol IN (...) ORDER BY timestamp DESC LIMIT 15 BY symbol
//     rồi AddClose theo thứ tự thời gian tăng dần.
//
// type RSI struct {
// 	period    int
// 	prevClose float64
// 	count     int
// 	avgGain   float64
// 	avgLoss   float64
// }
//
// func NewRSI(period int) *RSI
// func (r *RSI) AddClose(close float64)
// func (r *RSI) Ready() bool
// func (r *RSI) Value() float64
