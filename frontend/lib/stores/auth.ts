/**
 * Zustand auth store for managing authentication state.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { UserRead, Role } from '@/lib/types';
import { apiClient } from '@/lib/api/client';
import { USER_KEY } from '@/config/constants';

interface AuthStore {
  user: UserRead | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  setUser: (user: UserRead | null) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
  hasRole: (role: Role) => boolean;
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,

      setUser: (user: UserRead | null) => {
        set({
          user,
          isAuthenticated: !!user,
        });
      },

      setLoading: (loading: boolean) => {
        set({ isLoading: loading });
      },

      logout: () => {
        apiClient.clearToken();
        set({
          user: null,
          isAuthenticated: false,
        });
      },

      hasRole: (role: Role) => {
        const { user } = get();
        return user?.role === role;
      },
    }),
    {
      name: USER_KEY,
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
);
