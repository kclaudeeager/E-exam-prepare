'use client';

import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/hooks';
import { ROUTES } from '@/config/constants';

export default function AnalyticsPage() {
  const router = useRouter();
  const { user } = useAuth();

  if (!user || user.role !== 'admin') {
    router.push(ROUTES.DASHBOARD);
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="border-b bg-white shadow-sm">
        <div className="container py-4">
          <button
            onClick={() => router.back()}
            className="mb-2 text-blue-600 hover:underline"
          >
            ← Back
          </button>
          <h1 className="text-2xl font-bold text-gray-900">System Analytics</h1>
        </div>
      </header>

      {/* Content */}
      <main className="container py-8">
        <div className="card">
          <p className="text-gray-600">
            System analytics view coming soon. This page will show overall platform insights and
            trends.
          </p>
        </div>
      </main>
    </div>
  );
}
