import { createContext } from 'react'

export interface FavoritesContextType {
  favorites: string[]
  loading: boolean
  isFavorite: (symbol: string) => boolean
  toggleFavorite: (symbol: string) => Promise<boolean>
  refreshFavorites: () => Promise<void>
}

export const FavoritesContext = createContext<FavoritesContextType | null>(null)

