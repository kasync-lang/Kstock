import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import AuthCallbackPage from './pages/AuthCallbackPage'
import SymbolListPage from './pages/SymbolListPage'
import StockDetailPage from './pages/StockDetailPage'
import PortfolioPage from './pages/PortfolioPage'
import TradingPage from './pages/TradingPage'
import AlertsPage from './pages/AlertsPage'
import AccountPage from './pages/AccountPage'
import TempPage from './pages/TempPage'
import { FavoritesProvider, LivePriceProvider } from './context'

function App() {
  return (
    <BrowserRouter>
      <LivePriceProvider>
        <FavoritesProvider>
          <Routes>
            <Route path="/" element={<Navigate to="/symbols" replace />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route path="/auth/google/callback" element={<AuthCallbackPage />} />
            <Route path="/auth/callback" element={<AuthCallbackPage />} />
            <Route path="/oauth/exchange" element={<AuthCallbackPage />} />
            <Route path="/symbols" element={<SymbolListPage />} />
            <Route path="/stock/:symbol" element={<StockDetailPage />} />
            <Route path="/stock" element={<Navigate to="/symbols" replace />} />
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/trading" element={<TradingPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/temp" element={<TempPage />} />
            <Route path="*" element={<Navigate to="/symbols" replace />} />
          </Routes>
        </FavoritesProvider>
      </LivePriceProvider>
    </BrowserRouter>
  )
}

export default App
