'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks';
import { subjectAPI } from '@/lib/api';
import { SubjectRead } from '@/lib/types';
import { ROUTES } from '@/config/constants';

/**
 * Practice page — smart router for subject-based practice.
 *
 * Accepts optional query params:
 *   ?subject=Science&level=P6  → looks up subject, redirects to its workspace
 *   (no params)                → shows "choose a subject" guidance card
 *
 * Deep-link example:
 *   /student/practice?subject=Science%20and%20Elementary%20Technology&level=P6
 */
export default function PracticePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();

  const subjectParam = searchParams.get('subject');
  const levelParam = searchParams.get('level');

  const [status, setStatus] = useState<'idle' | 'searching' | 'not-found'>('idle');
  const [matchedSubjects, setMatchedSubjects] = useState<SubjectRead[]>([]);

  useEffect(() => {
    if (!user) {
      router.push(ROUTES.LOGIN);
      return;
    }

    // If subject + level are provided, look up the subject and redirect
    if (subjectParam && levelParam) {
      setStatus('searching');
      subjectAPI
        .list(levelParam)
        .then((subjects) => {
          const needle = subjectParam.toLowerCase().replace(/[_\s]+/g, ' ');
          const exact = subjects.find(
            (s) => s.name.toLowerCase().replace(/[_\s]+/g, ' ') === needle,
          );
          if (exact) {
            router.replace(`/student/subjects/${exact.id}?tab=practice`);
            return;
          }
          // Partial match
          const partial = subjects.filter(
            (s) => s.name.toLowerCase().includes(needle) || needle.includes(s.name.toLowerCase()),
          );
          if (partial.length === 1) {
            router.replace(`/student/subjects/${partial[0].id}?tab=practice`);
            return;
          }
          setMatchedSubjects(partial.length > 0 ? partial : subjects);
          setStatus('not-found');
        })
        .catch(() => setStatus('not-found'));
    }
  }, [user, subjectParam, levelParam, router]);

  if (!user) return null;

  // Searching state
  if (status === 'searching') {
    return (
      <main className="container py-8">
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
          <p className="text-sm text-gray-500">
            Finding {subjectParam} ({levelParam})…
          </p>
        </div>
      </main>
    );
  }

  // Subject not found — show available subjects
  if (status === 'not-found') {
    return (
      <main className="container py-8">
        <div className="mx-auto max-w-lg rounded-xl border bg-white p-8 text-center shadow-sm">
          <div className="text-5xl mb-4">🔍</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Subject Not Found</h1>
          <p className="text-gray-600 mb-4">
            Could not find <strong>{subjectParam}</strong> for <strong>{levelParam}</strong>.
          </p>
          {matchedSubjects.length > 0 && (
            <div className="mb-6">
              <p className="text-sm text-gray-500 mb-3">Did you mean one of these?</p>
              <div className="space-y-2">
                {matchedSubjects.slice(0, 6).map((s) => (
                  <Link
                    key={s.id}
                    href={`/student/subjects/${s.id}?tab=practice`}
                    className="block rounded-lg border p-3 text-left hover:border-blue-300 hover:bg-blue-50 transition-colors"
                  >
                    <span className="font-medium text-gray-900">
                      {s.icon || '📚'} {s.name}
                    </span>
                    <span className="ml-2 text-xs text-gray-400">{s.level}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
          <Link
            href={ROUTES.STUDENT_SUBJECTS}
            className="inline-block rounded-lg bg-blue-600 px-6 py-3 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            📚 Browse All Subjects
          </Link>
        </div>
      </main>
    );
  }

  // Default: no query params — guide user to subjects
  return (
    <main className="container py-8">
      <div className="mx-auto max-w-lg rounded-xl border bg-white p-8 text-center shadow-sm">
        <div className="text-5xl mb-4">📚</div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Practice by Subject</h1>
        <p className="text-gray-600 mb-6">
          Practice sessions are organized by subject. Choose a subject first, then start
          practicing with questions from all exam papers in that subject.
        </p>
        <div className="space-y-3">
          <Link
            href={ROUTES.STUDENT_SUBJECTS}
            className="block w-full rounded-lg bg-blue-600 px-6 py-3 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            📚 Go to Subjects →
          </Link>
          <p className="text-xs text-gray-400">
            Select a subject → open the Practice tab → choose Subject Practice or Real Exam Simulation
          </p>
        </div>
      </div>
    </main>
  );
}
