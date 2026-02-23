'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth, useAdminAnalytics } from '@/lib/hooks';
import { ROUTES } from '@/config/constants';

// ── KPI Card ──────────────────────────────────────────────────────────────

function KPICard({
  label,
  value,
  icon,
  color = 'blue',
  sub,
}: {
  label: string;
  value: string | number;
  icon: string;
  color?: 'blue' | 'green' | 'purple' | 'amber' | 'red' | 'cyan';
  sub?: string;
}) {
  const bgMap = {
    blue: 'bg-blue-50',
    green: 'bg-green-50',
    purple: 'bg-purple-50',
    amber: 'bg-amber-50',
    red: 'bg-red-50',
    cyan: 'bg-cyan-50',
  };
  const textMap = {
    blue: 'text-blue-600',
    green: 'text-green-600',
    purple: 'text-purple-600',
    amber: 'text-amber-600',
    red: 'text-red-600',
    cyan: 'text-cyan-600',
  };
  return (
    <div className={`rounded-xl ${bgMap[color]} p-4`}>
      <div className="flex items-center justify-between">
        <span className="text-2xl">{icon}</span>
        {sub && <span className="text-xs text-gray-400">{sub}</span>}
      </div>
      <p className={`mt-2 text-3xl font-bold ${textMap[color]}`}>{value}</p>
      <p className="text-sm text-gray-600">{label}</p>
    </div>
  );
}

// ── Accuracy Bar ──────────────────────────────────────────────────────────

function AccuracyBar({ label, value, count }: { label: string; value: number; count?: string }) {
  const pct = value * 100;
  const barColor =
    pct >= 70 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500';
  const textColor =
    pct >= 70 ? 'text-green-600' : pct >= 50 ? 'text-yellow-600' : 'text-red-600';
  return (
    <div className="flex items-center gap-3">
      <span className="w-32 truncate text-sm text-gray-700">{label}</span>
      <div className="flex-1">
        <div className="h-2.5 overflow-hidden rounded-full bg-gray-200">
          <div className={`h-full rounded-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
        </div>
      </div>
      <span className={`w-14 text-right text-sm font-semibold ${textColor}`}>{pct.toFixed(1)}%</span>
      {count && <span className="w-16 text-right text-xs text-gray-400">{count}</span>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [days, setDays] = useState(30);
  const { analytics, isLoading } = useAdminAnalytics(days);

  if (!user || user.role !== 'admin') {
    router.push(ROUTES.DASHBOARD);
    return null;
  }

  if (isLoading || !analytics) {
    return (
      <main className="container py-8">
        <h1 className="mb-6 text-2xl font-bold text-gray-900">📈 System Analytics</h1>
        <div className="py-16 text-center text-gray-500">Loading analytics…</div>
      </main>
    );
  }

  const { overview, subject_stats, trends, topic_stats, recent_attempts } = analytics;
  const pct = (v: number) => (v * 100).toFixed(1);

  return (
    <main className="container py-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📈 System Analytics</h1>
          <p className="text-sm text-gray-500">
            Platform-wide performance insights and usage trends.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">Trend window:</label>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
        </div>
      </div>

      {/* KPI grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KPICard icon="👥" label="Total Students" value={overview.total_students} color="blue" />
        <KPICard icon="📄" label="Documents" value={overview.total_documents} color="purple" />
        <KPICard icon="❓" label="Questions" value={overview.total_questions} color="cyan" />
        <KPICard icon="📝" label="Total Attempts" value={overview.total_attempts} color="green" />
        <KPICard icon="🎯" label="Avg Accuracy" value={`${pct(overview.avg_accuracy)}%`} color="amber" />
        <KPICard icon="🔥" label="Active (7d)" value={overview.active_students_7d} color="red" sub={`of ${overview.total_students}`} />
        <KPICard icon="📅" label="Active (30d)" value={overview.active_students_30d} color="blue" sub={`of ${overview.total_students}`} />
        <KPICard icon="🛡️" label="Admins" value={overview.total_admins} color="purple" />
      </div>

      {/* Two-column layout: Subject Stats + Topic Breakdown */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Subject stats */}
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">📚 Subject Overview</h2>
          {subject_stats.length === 0 ? (
            <p className="text-sm text-gray-400">No subjects yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b">
                  <tr>
                    <th className="pb-2 text-left font-medium text-gray-600">Subject</th>
                    <th className="pb-2 text-right font-medium text-gray-600">Docs</th>
                    <th className="pb-2 text-right font-medium text-gray-600">Questions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {subject_stats.map((ss) => (
                    <tr key={ss.subject} className="hover:bg-gray-50">
                      <td className="py-2 text-gray-700">{ss.subject}</td>
                      <td className="py-2 text-right text-gray-700">{ss.document_count}</td>
                      <td className="py-2 text-right text-gray-700">{ss.question_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Topic breakdown */}
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">🏷️ Topic Performance</h2>
          {topic_stats.length === 0 ? (
            <p className="text-sm text-gray-400">No topic data yet.</p>
          ) : (
            <div className="space-y-3">
              {topic_stats.slice(0, 12).map((ts) => (
                <AccuracyBar
                  key={ts.topic}
                  label={ts.topic}
                  value={ts.avg_accuracy}
                  count={`${ts.student_count} stu`}
                />
              ))}
              {topic_stats.length > 12 && (
                <p className="text-center text-xs text-gray-400">
                  + {topic_stats.length - 12} more topics
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Activity trends */}
      {trends.length > 0 && (
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">📊 Activity Trends</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr>
                  <th className="pb-2 text-left font-medium text-gray-600">Date</th>
                  <th className="pb-2 text-right font-medium text-gray-600">Attempts</th>
                  <th className="pb-2 text-right font-medium text-gray-600">Avg Accuracy</th>
                  <th className="pb-2 text-right font-medium text-gray-600">Active Students</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {trends.map((t) => (
                  <tr key={t.date} className="hover:bg-gray-50">
                    <td className="py-2 text-gray-700">{new Date(t.date).toLocaleDateString()}</td>
                    <td className="py-2 text-right text-gray-700">{t.attempts}</td>
                    <td className={`py-2 text-right font-medium ${
                      t.avg_accuracy * 100 >= 70
                        ? 'text-green-600'
                        : t.avg_accuracy * 100 >= 50
                          ? 'text-yellow-600'
                          : 'text-red-600'
                    }`}>
                      {pct(t.avg_accuracy)}%
                    </td>
                    <td className="py-2 text-right text-gray-700">{t.active_students}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent attempts feed */}
      <div className="rounded-xl border bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">🕐 Recent Activity</h2>
        {recent_attempts.length === 0 ? (
          <p className="text-sm text-gray-400">No recent attempts.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr>
                  <th className="pb-2 text-left font-medium text-gray-600">Student</th>
                  <th className="pb-2 text-right font-medium text-gray-600">Score</th>
                  <th className="pb-2 text-right font-medium text-gray-600">%</th>
                  <th className="hidden pb-2 text-right font-medium text-gray-600 sm:table-cell">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {recent_attempts.map((a) => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="py-2 text-gray-700">{a.student_name}</td>
                    <td className="py-2 text-right text-gray-700">{a.score}/{a.total}</td>
                    <td className={`py-2 text-right font-medium ${
                      a.percentage >= 70
                        ? 'text-green-600'
                        : a.percentage >= 50
                          ? 'text-yellow-600'
                          : 'text-red-600'
                    }`}>
                      {a.percentage.toFixed(1)}%
                    </td>
                    <td className="hidden py-2 text-right text-xs text-gray-500 sm:table-cell">
                      {a.submitted_at ? new Date(a.submitted_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
