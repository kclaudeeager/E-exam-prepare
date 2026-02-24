'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks';
import { ROUTES } from '@/config/constants';

export default function DashboardPage() {
  const { user, fetchCurrentUser, isAuthenticated } = useAuth();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      if (!isAuthenticated && !user) {
        await fetchCurrentUser();
      }
      setLoading(false);
    };
    initAuth();
  }, [isAuthenticated, user, fetchCurrentUser]);

  if (loading) {
    return (
      <div className="flex-center min-h-screen">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  if (!user) return null;

  const isStudent = user.role === 'student';
  const isAdmin = user.role === 'admin';

  return (
    <>
      {/* Content */}
      <main className="container py-8">
        {isStudent && (
          <div className="space-y-6">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-xl font-bold text-gray-900">Student Dashboard</h2>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">Level:</span>
                {user.education_level ? (
                  <span className="rounded-full bg-green-100 px-3 py-0.5 text-sm font-semibold text-green-700">
                    {user.education_level}
                  </span>
                ) : (
                  <Link
                    href={ROUTES.STUDENT_PROFILE}
                    className="rounded-full bg-yellow-100 px-3 py-0.5 text-sm font-semibold text-yellow-700 hover:bg-yellow-200 transition-colors"
                  >
                    ⚠️ Set your level →
                  </Link>
                )}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <Link href={ROUTES.STUDENT_BROWSE}>
                <div className="card cursor-pointer hover:shadow-md border-blue-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">Exam Papers</h3>
                      <p className="text-sm text-gray-600">Browse past exam papers</p>
                    </div>
                    <div className="text-3xl">📄</div>
                  </div>
                </div>
              </Link>

              <Link href={ROUTES.STUDENT_DOCUMENTS}>
                <div className="card cursor-pointer hover:shadow-md border-indigo-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">My Documents</h3>
                      <p className="text-sm text-gray-600">Upload &amp; manage your materials</p>
                    </div>
                    <div className="text-3xl">📂</div>
                  </div>
                </div>
              </Link>

              <Link href={ROUTES.STUDENT_ASK_AI}>
                <div className="card cursor-pointer hover:shadow-md border-purple-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">Ask AI</h3>
                      <p className="text-sm text-gray-600">Get AI explanations from exam papers</p>
                    </div>
                    <div className="text-3xl">🤖</div>
                  </div>
                </div>
              </Link>

              <Link href={ROUTES.STUDENT_PRACTICE}>
                <div className="card cursor-pointer hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">Practice Quizzes</h3>
                      <p className="text-sm text-gray-600">Test yourself with adaptive quizzes</p>
                    </div>
                    <div className="text-3xl">📝</div>
                  </div>
                </div>
              </Link>

              <Link href={ROUTES.STUDENT_PROGRESS}>
                <div className="card cursor-pointer hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">Your Progress</h3>
                      <p className="text-sm text-gray-600">View your learning analytics</p>
                    </div>
                    <div className="text-3xl">📊</div>
                  </div>
                </div>
              </Link>

              <Link href={ROUTES.STUDENT_ATTEMPTS}>
                <div className="card cursor-pointer hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">Past Attempts</h3>
                      <p className="text-sm text-gray-600">Review your quiz history</p>
                    </div>
                    <div className="text-3xl">📚</div>
                  </div>
                </div>
              </Link>

              <Link href={ROUTES.STUDENT_PROFILE}>
                <div className="card cursor-pointer hover:shadow-md border-gray-100">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">My Profile</h3>
                      <p className="text-sm text-gray-600">View and edit your details</p>
                    </div>
                    <div className="text-3xl">👤</div>
                  </div>
                </div>
              </Link>
            </div>
          </div>
        )}

        {isAdmin && (
          <div className="space-y-6">
            <h2 className="text-xl font-bold text-gray-900">Admin Dashboard</h2>

            <div className="grid gap-4 md:grid-cols-3">
              <Link href={ROUTES.ADMIN_DOCUMENTS}>
                <div className="card cursor-pointer hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">Documents</h3>
                      <p className="text-sm text-gray-600">Upload and manage exams</p>
                    </div>
                    <div className="text-3xl">📄</div>
                  </div>
                </div>
              </Link>

              <Link href={ROUTES.ADMIN_STUDENTS}>
                <div className="card cursor-pointer hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">Students</h3>
                      <p className="text-sm text-gray-600">Monitor student progress</p>
                    </div>
                    <div className="text-3xl">👥</div>
                  </div>
                </div>
              </Link>

              <Link href={ROUTES.ADMIN_ANALYTICS}>
                <div className="card cursor-pointer hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">Analytics</h3>
                      <p className="text-sm text-gray-600">System-wide insights</p>
                    </div>
                    <div className="text-3xl">📈</div>
                  </div>
                </div>
              </Link>
            </div>
          </div>
        )}
      </main>
    </>
  );
}
