'use client';

import Link from 'next/link';
import { useAuth } from '@/lib/hooks';
import { ROUTES } from '@/config/constants';

export default function HomePage() {
  const { isAuthenticated, logout } = useAuth();

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Header */}
      <header className="border-b bg-white shadow-sm">
        <div className="container flex-between py-4">
          <h1 className="text-2xl font-bold text-gray-900">E-exam-prepare</h1>
          <nav className="flex items-center gap-4">
            {isAuthenticated ? (
              <>
                <Link href={ROUTES.DASHBOARD} className="text-blue-600 hover:underline">
                  Dashboard
                </Link>
                <button
                  onClick={logout}
                  className="rounded bg-red-600 px-4 py-2 text-white hover:bg-red-700"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link href={ROUTES.LOGIN} className="text-blue-600 hover:underline">
                  Sign In
                </Link>
                <Link
                  href={ROUTES.REGISTER}
                  className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
                >
                  Sign Up
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      {/* Hero */}
      <main className="container flex flex-col items-center justify-center py-20 text-center">
        <h2 className="text-4xl font-bold text-gray-900">
          Personalized Exam Preparation
        </h2>
        <p className="mt-4 max-w-2xl text-xl text-gray-600">
          Master your exams with AI-powered adaptive learning, intelligent quizzes, and detailed
          performance analytics.
        </p>

        <div className="mt-8 flex gap-4">
          {!isAuthenticated && (
            <>
              <Link
                href={ROUTES.REGISTER}
                className="rounded bg-blue-600 px-8 py-3 text-lg font-semibold text-white hover:bg-blue-700"
              >
                Get Started Free
              </Link>
              <Link
                href={ROUTES.LOGIN}
                className="rounded border-2 border-blue-600 px-8 py-3 text-lg font-semibold text-blue-600 hover:bg-blue-50"
              >
                Sign In
              </Link>
            </>
          )}
        </div>

        {/* Features */}
        <div className="mt-20 grid gap-8 md:grid-cols-3">
          <div className="card">
            <div className="text-4xl">🎯</div>
            <h3 className="mt-4 font-semibold text-gray-900">Adaptive Learning</h3>
            <p className="mt-2 text-gray-600">
              Our system learns your weak areas and recommends targeted practice.
            </p>
          </div>

          <div className="card">
            <div className="text-4xl">📊</div>
            <h3 className="mt-4 font-semibold text-gray-900">Real-time Analytics</h3>
            <p className="mt-2 text-gray-600">
              Track progress with detailed performance metrics and insights.
            </p>
          </div>

          <div className="card">
            <div className="text-4xl">⚡</div>
            <h3 className="mt-4 font-semibold text-gray-900">Smart Explanations</h3>
            <p className="mt-2 text-gray-600">
              Get AI-generated solutions powered by RAG technology.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
