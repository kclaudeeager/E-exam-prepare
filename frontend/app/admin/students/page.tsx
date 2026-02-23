'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth, useAdminStudents, useAdminStudentDetail } from '@/lib/hooks';
import { ROUTES } from '@/config/constants';
import { StudentSummary } from '@/lib/types';

// ── Student Detail Panel ──────────────────────────────────────────────────

function StudentDetailPanel({
  studentId,
  onClose,
}: {
  studentId: string;
  onClose: () => void;
}) {
  const { student, isLoading } = useAdminStudentDetail(studentId);

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div className="w-full max-w-2xl rounded-xl bg-white p-8 shadow-2xl">
          <p className="text-center text-gray-500">Loading student details…</p>
        </div>
      </div>
    );
  }

  if (!student) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div className="w-full max-w-2xl rounded-xl bg-white p-8 shadow-2xl">
          <p className="text-center text-red-500">Student not found.</p>
          <button onClick={onClose} className="mt-4 text-blue-600 hover:underline">
            Close
          </button>
        </div>
      </div>
    );
  }

  const pct = (v: number) => (v * 100).toFixed(1);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="relative mx-4 max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-2xl text-gray-400 hover:text-gray-600"
        >
          ×
        </button>

        {/* Header */}
        <div className="mb-6">
          <h2 className="text-xl font-bold text-gray-900">{student.full_name}</h2>
          <p className="text-sm text-gray-500">{student.email}</p>
          <div className="mt-2 flex gap-2">
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              student.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            }`}>
              {student.is_active ? 'Active' : 'Inactive'}
            </span>
            <span className="text-xs text-gray-400">
              Joined {new Date(student.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>

        {/* Summary cards */}
        <div className="mb-6 grid grid-cols-3 gap-3">
          <div className="rounded-lg bg-blue-50 p-3 text-center">
            <p className="text-2xl font-bold text-blue-600">{pct(student.overall_accuracy)}%</p>
            <p className="text-xs text-blue-600/70">Overall Accuracy</p>
          </div>
          <div className="rounded-lg bg-purple-50 p-3 text-center">
            <p className="text-2xl font-bold text-purple-600">{student.total_attempts}</p>
            <p className="text-xs text-purple-600/70">Total Attempts</p>
          </div>
          <div className="rounded-lg bg-amber-50 p-3 text-center">
            <p className="text-2xl font-bold text-amber-600">{student.weak_topics.length}</p>
            <p className="text-xs text-amber-600/70">Weak Topics</p>
          </div>
        </div>

        {/* Weak topics */}
        {student.weak_topics.length > 0 && (
          <div className="mb-6">
            <h3 className="mb-2 text-sm font-semibold text-gray-700">⚠️ Weak Topics</h3>
            <div className="flex flex-wrap gap-2">
              {student.weak_topics.map((topic) => (
                <span key={topic} className="rounded-full bg-yellow-100 px-3 py-1 text-xs text-yellow-800">
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Topic metrics */}
        {student.topic_metrics.length > 0 && (
          <div className="mb-6">
            <h3 className="mb-2 text-sm font-semibold text-gray-700">📊 Topic Performance</h3>
            <div className="space-y-2">
              {student.topic_metrics.map((m) => (
                <div key={m.topic} className="flex items-center gap-3">
                  <span className="w-28 truncate text-sm text-gray-700">{m.topic}</span>
                  <div className="flex-1">
                    <div className="h-2 overflow-hidden rounded bg-gray-200">
                      <div
                        className={`h-full transition-all ${
                          m.accuracy * 100 >= 70
                            ? 'bg-green-500'
                            : m.accuracy * 100 >= 60
                              ? 'bg-yellow-500'
                              : 'bg-red-500'
                        }`}
                        style={{ width: `${m.accuracy * 100}%` }}
                      />
                    </div>
                  </div>
                  <span className={`w-14 text-right text-sm font-medium ${
                    m.accuracy * 100 >= 70
                      ? 'text-green-600'
                      : m.accuracy * 100 >= 60
                        ? 'text-yellow-600'
                        : 'text-red-600'
                  }`}>
                    {pct(m.accuracy)}%
                  </span>
                  <span className="w-16 text-right text-xs text-gray-400">{m.attempts} att.</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent attempts */}
        {student.recent_attempts.length > 0 && (
          <div>
            <h3 className="mb-2 text-sm font-semibold text-gray-700">📝 Recent Attempts</h3>
            <div className="overflow-hidden rounded-lg border">
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-gray-600">Date</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-600">Score</th>
                    <th className="px-3 py-2 text-right font-medium text-gray-600">%</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {student.recent_attempts.map((a) => (
                    <tr key={a.id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-gray-700">
                        {a.submitted_at
                          ? new Date(a.submitted_at).toLocaleDateString()
                          : new Date(a.started_at).toLocaleDateString()}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-700">
                        {a.score}/{a.total}
                      </td>
                      <td className={`px-3 py-2 text-right font-medium ${
                        a.percentage >= 70
                          ? 'text-green-600'
                          : a.percentage >= 50
                            ? 'text-yellow-600'
                            : 'text-red-600'
                      }`}>
                        {a.percentage.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {student.topic_metrics.length === 0 && student.recent_attempts.length === 0 && (
          <p className="text-center text-sm text-gray-400">No activity yet for this student.</p>
        )}
      </div>
    </div>
  );
}

// ── Accuracy badge ────────────────────────────────────────────────────────

function AccuracyBadge({ value }: { value: number }) {
  const pct = value * 100;
  const color =
    pct >= 70
      ? 'text-green-700 bg-green-50'
      : pct >= 50
        ? 'text-yellow-700 bg-yellow-50'
        : 'text-red-700 bg-red-50';
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-sm font-semibold ${color}`}>
      {pct.toFixed(1)}%
    </span>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────

export default function StudentsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);

  const { students, isLoading } = useAdminStudents(debouncedSearch);

  if (!user || user.role !== 'admin') {
    router.push(ROUTES.DASHBOARD);
    return null;
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setDebouncedSearch(search);
  };

  return (
    <>
      <main className="container py-8">
        {/* Page header */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">👥 Student Management</h1>
            <p className="text-sm text-gray-500">
              View and monitor all registered students and their learning progress.
            </p>
          </div>
          <div className="rounded-lg bg-blue-50 px-4 py-2 text-center">
            <p className="text-2xl font-bold text-blue-600">{students.length}</p>
            <p className="text-xs text-blue-600/70">Total Students</p>
          </div>
        </div>

        {/* Search bar */}
        <form onSubmit={handleSearch} className="mb-6">
          <div className="flex gap-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or email…"
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700"
            >
              Search
            </button>
            {debouncedSearch && (
              <button
                type="button"
                onClick={() => { setSearch(''); setDebouncedSearch(''); }}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
              >
                Clear
              </button>
            )}
          </div>
        </form>

        {/* Student table */}
        {isLoading ? (
          <div className="py-16 text-center text-gray-500">Loading students…</div>
        ) : students.length === 0 ? (
          <div className="rounded-xl border bg-white p-8 text-center">
            <p className="text-gray-500">
              {debouncedSearch
                ? `No students matching "${debouncedSearch}"`
                : 'No students registered yet.'}
            </p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-600">Student</th>
                    <th className="px-4 py-3 text-right font-medium text-gray-600">Attempts</th>
                    <th className="px-4 py-3 text-right font-medium text-gray-600">Accuracy</th>
                    <th className="hidden px-4 py-3 text-right font-medium text-gray-600 md:table-cell">Last Active</th>
                    <th className="hidden px-4 py-3 text-right font-medium text-gray-600 sm:table-cell">Status</th>
                    <th className="px-4 py-3 text-right font-medium text-gray-600">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {students.map((s: StudentSummary) => (
                    <tr key={s.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-medium text-gray-900">{s.full_name}</p>
                          <p className="text-xs text-gray-400">{s.email}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right text-gray-700">{s.total_attempts}</td>
                      <td className="px-4 py-3 text-right">
                        <AccuracyBadge value={s.overall_accuracy} />
                      </td>
                      <td className="hidden px-4 py-3 text-right text-xs text-gray-500 md:table-cell">
                        {s.last_attempt_at
                          ? new Date(s.last_attempt_at).toLocaleDateString()
                          : 'Never'}
                      </td>
                      <td className="hidden px-4 py-3 text-right sm:table-cell">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          s.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                        }`}>
                          {s.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => setSelectedStudentId(s.id)}
                          className="rounded bg-blue-50 px-3 py-1 text-xs font-medium text-blue-600 hover:bg-blue-100"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* Student detail modal */}
      {selectedStudentId && (
        <StudentDetailPanel
          studentId={selectedStudentId}
          onClose={() => setSelectedStudentId(null)}
        />
      )}
    </>
  );
}
