import { useEffect, useState, useCallback, useMemo } from 'react'
import type { ReactNode } from 'react'
import { addFavorite as apiAddFavorite, getFavorites, removeFavorite as apiRemoveFavorite } from '../services/favorite.service'
import { getToken } from '../services/api'
import { FavoritesContext } from './favorites.context'

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const [favorites, setFavorites] = useState<string[]>([])
  const [loading, setLoading] = useState<boolean>(false)

  useEffect(() => {
    let isMounted = true
    if (!getToken()) return

    async function loadInitial() {
      try {
        const res = await getFavorites()
        if (isMounted) {
          setFavorites((res.data ?? []).map((s) => s.toUpperCase()))
        }
      } catch {
        if (isMounted) setFavorites([])
      }
    }

    loadInitial()
    return () => {
      isMounted = false
    }
  }, [])

  const refreshFavorites = useCallback(async () => {
    if (!getToken()) {
      setFavorites([])
      return
    }
    setLoading(true)
    try {
      const res = await getFavorites()
      setFavorites((res.data ?? []).map((s) => s.toUpperCase()))
    } catch {
      setFavorites([])
    } finally {
      setLoading(false)
    }
  }, [])

  const isFavorite = useCallback(
    (symbol: string) => {
      const upper = symbol.toUpperCase()
      return favorites.includes(upper)
    },
    [favorites],
  )

  const toggleFavorite = useCallback(
    async (symbol: string): Promise<boolean> => {
      const upper = symbol.toUpperCase()
      const alreadyFav = favorites.includes(upper)

      if (alreadyFav) {
        setFavorites((prev) => prev.filter((s) => s !== upper))
      } else {
        setFavorites((prev) => [...prev, upper])
      }

      try {
        if (alreadyFav) {
          await apiRemoveFavorite(upper)
          return false
        } else {
          await apiAddFavorite(upper)
          return true
        }
      } catch (err) {
        if (alreadyFav) {
          setFavorites((prev) => [...prev, upper])
        } else {
          setFavorites((prev) => prev.filter((s) => s !== upper))
        }
        throw err
      }
    },
    [favorites],
  )

  const value = useMemo(
    () => ({
      favorites,
      loading,
      isFavorite,
      toggleFavorite,
      refreshFavorites,
    }),
    [favorites, loading, isFavorite, toggleFavorite, refreshFavorites],
  )

  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>
}

