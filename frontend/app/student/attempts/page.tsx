'use client';

import { useRouter } from 'next/navigation';
import { useAuth, useAttempts } from '@/lib/hooks';
import { ROUTES } from '@/config/constants';

export default function AttemptsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { attempts, isLoading } = useAttempts();

  if (!user) {
    router.push(ROUTES.LOGIN);
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
          <h1 className="text-2xl font-bold text-gray-900">Past Attempts</h1>
        </div>
      </header>

      {/* Content */}
      <main className="container py-8">
        {isLoading ? (
          <div className="flex-center">
            <div className="text-gray-600">Loading attempts...</div>
          </div>
        ) : attempts.length > 0 ? (
          <div className="space-y-4">
            {attempts.map((attempt) => (
              <div
                key={attempt.id}
                className="card cursor-pointer hover:shadow-md"
                onClick={() => router.push(ROUTES.STUDENT_ATTEMPT_DETAIL(attempt.id))}
              >
                <div className="flex-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900">
                      Quiz • {attempt.submitted_at
                        ? new Date(attempt.submitted_at).toLocaleDateString()
                        : new Date(attempt.started_at).toLocaleDateString()}
                    </h3>
                    <p className="text-sm text-gray-600">
                      {attempt.topic_breakdown.length} topic(s) •{' '}
                      {attempt.submitted_at
                        ? new Date(attempt.submitted_at).toLocaleTimeString()
                        : 'In progress'}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={`text-2xl font-bold ${
                      attempt.percentage >= 70
                        ? 'text-green-600'
                        : attempt.percentage >= 50
                          ? 'text-yellow-600'
                          : 'text-red-600'
                    }`}>
                      {attempt.percentage.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-600">
                      {attempt.score}/{attempt.total}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="card text-center">
            <p className="text-gray-600 mb-4">No attempts yet. Start a quiz to get started!</p>
            <button
              onClick={() => router.push(ROUTES.STUDENT_PRACTICE)}
              className="rounded bg-blue-600 px-6 py-2 text-white hover:bg-blue-700"
            >
              Start Practicing
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
