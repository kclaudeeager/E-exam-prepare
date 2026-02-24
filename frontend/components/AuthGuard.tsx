'use client';

/**
 * AuthGuard – waits for Zustand persist hydration before deciding whether
 * to render children or redirect to /login.
 *
 * Wrapping a route-level layout with <AuthGuard> fixes the "new tab logs
 * out the user" problem: on first render the store hasn't rehydrated from
 * localStorage yet so user is temporarily null.  We show a loading spinner
 * instead of immediately redirecting.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth';
import { ROUTES } from '@/config/constants';
import { Role } from '@/lib/types';

interface AuthGuardProps {
  children: React.ReactNode;
  /** If provided, also checks that the authenticated user has this role. */
  requireRole?: Role;
}

export default function AuthGuard({ children, requireRole }: AuthGuardProps) {
  const router = useRouter();
  const { user, isAuthenticated, hasHydrated } = useAuthStore();

  useEffect(() => {
    if (!hasHydrated) return; // still reading from localStorage – wait

    if (!isAuthenticated || !user) {
      router.replace(ROUTES.LOGIN);
      return;
    }

    if (requireRole && user.role !== requireRole) {
      // Wrong role – send them to their own dashboard
      router.replace(ROUTES.DASHBOARD);
    }
  }, [hasHydrated, isAuthenticated, user, requireRole, router]);

  // Not yet hydrated → neutral loading screen (no flash of redirect)
  if (!hasHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          <p className="text-sm text-gray-500">Loading…</p>
        </div>
      </div>
    );
  }

  // Hydrated but not authenticated (redirect is firing in useEffect)
  if (!isAuthenticated || !user) return null;

  // Hydrated, authenticated, correct role (or no role required)
  if (requireRole && user.role !== requireRole) return null;

  return <>{children}</>;
}
