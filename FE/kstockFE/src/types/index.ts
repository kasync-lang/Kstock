// ─── Auth (AuthenApp /api/v1) ────────────────────────────────────────────────

export interface Token {
  access_token: string
  session_token?: string
  token_type?: string
}

export interface UserRegister {
  email: string
  password: string
  full_name?: string
}

export interface UserUpdateMe {
  email: string
  full_name: string
}

export interface UpdatePassword {
  current_password: string
  new_password: string
}

export interface UserPublic {
  id: string
  email: string
  full_name?: string
  is_active?: boolean
  is_superuser?: boolean
  provider?: string | null
}

export interface NewPassword {
  token: string
  new_password: string
}

export interface Message {
  message: string
}

// ─── Symbols (InteractionApp /api/symbols) ────────────────────────────────────

export interface SymbolPublic {
  ticker: string
  name: string
  logo: string
}

export interface SymbolPreview extends SymbolPublic {
  lastPrice: number
  percentChange: number
}

export interface SymbolBaseDetail {
  country: string
  currency: string
  exchange: string
  ipo: string
  marketCapitalization: number
  name: string
  phone: string
  shareOutstanding: number
  ticker: string
  weburl: string
  logo: string
  industry: string
}

export interface QuerySymbol {
  /** Symbol or company name prefix to search (default: '') */
  name?: string
  /** Exchange filter (default: 'NASDAQ') */
  exchange?: string
  /** Sort field: 'name' | 'market_cap' | 'ipo' (default: 'name') */
  order_by?: 'name' | 'market_cap' | 'ipo'
}

// ─── Favorites (InteractionApp /api/favorites) ────────────────────────────────

export interface FavoritesResponse {
  data: string[]
}

// ─── Notes (InteractionApp /api/notes) ────────────────────────────────────────

export interface NoteCreate {
  symbol: string
  title: string
  content: string
}

export interface NotePublic {
  id: string
  title: string
}

export interface NoteDetail extends NotePublic {
  symbol: string
  content: string
  created_at: string
  updated_at: string
}

export interface NoteUpdate {
  id: string
  title?: string
  content?: string
}

// ─── Alerts (InteractionApp /api/alerts) ─────────────────────────────────────

export interface Trigger {
  indicator: string
  /** Operator / condition, e.g. ">" | "<" | "==" | ">=" | "<=" */
  operator?: string
  condition?: string
  threshold: number | null
}

export interface AlertCreate {
  symbol: string
  active: boolean
  triggers: Trigger[]
}

export interface AlertDetail {
  id: number | string
  symbol: string
  active?: boolean
  status?: boolean
  created_at: string
  updated_at: string
  triggers: Trigger[]
}

// ─── Assets (InteractionApp /api/assets) ──────────────────────────────────────

export interface Asset {
  symbol: string
  quantity: number
  price: number
  profit_and_loss: number
  market_value: number
}

export interface AssetsResponse {
  data: Asset[]
  all_profit_and_loss: number
  cash_balance: number
}

export interface CashBalanceResponse {
  cash_balance: number
}

export interface TopupRequest {
  amount: number
}

export interface TopupResponse {
  message: string
  amount: number
  new_cash_balance: number
}

// ─── Transactions (InteractionApp /api/transactions) ──────────────────────────

export type OrderOperation = 'BUY' | 'SELL'

export interface Order {
  symbol: string
  quantity: number
  operation: OrderOperation
}

export interface BuyOrderResponse {
  message: string
  symbol: string
  amount: number
  price: number
  total_cost: number
  new_cash_balance: number
  new_unit_price: number
  total_holdings: number
}

export interface SellOrderResponse {
  message: string
  symbol: string
  amount: number
  price: number
  total_proceeds: number
  new_cash_balance: number
  remaining_holdings: number
}

export interface TransactionHistoryItem {
  id: string
  amount: number
  symbol: string
  operation: OrderOperation | string
  price: number
  time_transacted: string
}

export interface TransactionHistoryResponse {
  data: TransactionHistoryItem[]
  page: number
  page_size: number
  total: number
  total_pages: number
  has_next: boolean
}

// ─── Chart History (InteractionApp /api/chart/history) ───────────────────────

export type ChartResolution = '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1D' | '1W' | '1M' | string

export interface ChartHistoryQueryParams {
  symbol: string
  resolution: ChartResolution
  /** Unix timestamp in seconds */
  from: number
  /** Unix timestamp in seconds */
  to: number
}

export interface OHLCVResponse {
  s: string
  t: number[]
  o: number[]
  h: number[]
  l: number[]
  c: number[]
  v: number[]
}
