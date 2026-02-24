'use client';

/**
 * Auth layout – if user is already authenticated, redirect to dashboard.
 * Prevents logged-in users from seeing /login or /register.
 */

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth';
import { ROUTES } from '@/config/constants';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, hasHydrated } = useAuthStore();

  useEffect(() => {
    if (hasHydrated && isAuthenticated) {
      router.replace(ROUTES.DASHBOARD);
    }
  }, [hasHydrated, isAuthenticated, router]);

  // While hydrating, render nothing to avoid flash of login form
  if (!hasHydrated) return null;

  // Already authenticated – useEffect will redirect, show nothing
  if (isAuthenticated) return null;

  return <>{children}</>;
}
