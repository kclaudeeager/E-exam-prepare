'use client';

import { useRouter } from 'next/navigation';
import { useAuth, useProgress } from '@/lib/hooks';
import { ROUTES } from '@/config/constants';

export default function ProgressPage() {
  const router = useRouter();
  const { user } = useAuth();
  const { progress, isLoading } = useProgress();

  if (!user) {
    router.push(ROUTES.LOGIN);
    return null;
  }

  // Backend returns accuracy as 0-1 fraction; convert to percentage for display
  const pct = (val: number) => val * 100;

  return (
    <main className="container py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Your Progress</h1>
        {isLoading ? (
          <div className="flex-center">
            <div className="text-gray-600">Loading progress...</div>
          </div>
        ) : progress ? (
          <div className="space-y-6">
            {/* Overall Stats */}
            <div className="grid gap-4 md:grid-cols-3">
              <div className="card">
                <div className="text-center">
                  <p className="text-sm font-medium text-gray-600">Overall Accuracy</p>
                  <p className="text-3xl font-bold text-blue-600">
                    {pct(progress.overall_accuracy).toFixed(1)}%
                  </p>
                </div>
              </div>
              <div className="card">
                <div className="text-center">
                  <p className="text-sm font-medium text-gray-600">Total Attempts</p>
                  <p className="text-3xl font-bold text-gray-900">
                    {progress.total_attempts}
                  </p>
                </div>
              </div>
              <div className="card">
                <div className="text-center">
                  <p className="text-sm font-medium text-gray-600">Topics</p>
                  <p className="text-3xl font-bold text-gray-900">
                    {progress.topic_metrics.length}
                  </p>
                </div>
              </div>
            </div>

            {/* Weak Topics */}
            {progress.weak_topics.length > 0 && (
              <div className="card">
                <h3 className="mb-4 font-semibold text-gray-900">Areas to Improve</h3>
                <ul className="space-y-2">
                  {progress.weak_topics.map((topic) => (
                    <li key={topic} className="flex items-center">
                      <span className="mr-2 text-yellow-500">⚠️</span>
                      <span className="text-gray-700">{topic}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recommendations */}
            {progress.recommendations.length > 0 && (
              <div className="card">
                <h3 className="mb-4 font-semibold text-gray-900">Recommendations</h3>
                <ul className="space-y-2">
                  {progress.recommendations.map((rec, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="mr-2 text-green-500">✓</span>
                      <span className="text-gray-700">{rec}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Topic Metrics */}
            {progress.topic_metrics.length > 0 && (
              <div className="card">
                <h3 className="mb-4 font-semibold text-gray-900">Per-Topic Performance</h3>
                <div className="space-y-3">
                  {progress.topic_metrics.map((metric) => (
                    <div key={metric.topic} className="border-b pb-3 last:border-b-0">
                      <div className="flex-between mb-2">
                        <div>
                          <p className="font-medium text-gray-900">{metric.topic}</p>
                          <p className="text-xs text-gray-600">
                            {metric.attempts} attempt(s)
                            {metric.last_attempted &&
                              ` • Last: ${new Date(metric.last_attempted).toLocaleDateString()}`}
                          </p>
                        </div>
                        <div className="text-right">
                          <p
                            className={`font-bold ${
                              pct(metric.accuracy) >= 70
                                ? 'text-green-600'
                                : pct(metric.accuracy) >= 60
                                  ? 'text-yellow-600'
                                  : 'text-red-600'
                            }`}
                          >
                            {pct(metric.accuracy).toFixed(1)}%
                          </p>
                        </div>
                      </div>
                      {/* Progress bar */}
                      <div className="h-2 overflow-hidden rounded bg-gray-200">
                        <div
                          className={`h-full transition-all ${
                            pct(metric.accuracy) >= 70
                              ? 'bg-green-500'
                              : pct(metric.accuracy) >= 60
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                          }`}
                          style={{ width: `${pct(metric.accuracy)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Last Activity */}
            {progress.last_attempt_at && (
              <p className="text-center text-sm text-gray-500">
                Last activity: {new Date(progress.last_attempt_at).toLocaleString()}
              </p>
            )}
          </div>
        ) : (
          <div className="card text-center">
            <p className="text-gray-600 mb-4">No progress data yet. Start a quiz to begin!</p>
            <button
              onClick={() => router.push(ROUTES.STUDENT_PRACTICE)}
              className="rounded bg-blue-600 px-6 py-2 text-white hover:bg-blue-700"
            >
              Start Practicing
            </button>
          </div>
        )}
    </main>
  );
}
