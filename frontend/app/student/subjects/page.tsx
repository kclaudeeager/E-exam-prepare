'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth, useSubjects } from '@/lib/hooks';
import { ROUTES, EDUCATION_LEVELS } from '@/config/constants';
import { SubjectRead } from '@/lib/types';

export default function SubjectsPage() {
  const { user } = useAuth();
  const [filterLevel, setFilterLevel] = useState<string>(user?.education_level || '');
  const { subjects, isLoading, enroll, unenroll } = useSubjects(filterLevel || undefined);
  const [enrollingId, setEnrollingId] = useState<string | null>(null);

  useEffect(() => {
    if (user?.education_level && !filterLevel) {
      setFilterLevel(user.education_level);
    }
  }, [user, filterLevel]);

  if (!user) return null;

  const enrolledSubjects = subjects.filter((s) => s.enrolled);
  const availableSubjects = subjects.filter((s) => !s.enrolled);

  const handleEnroll = async (subjectId: string) => {
    setEnrollingId(subjectId);
    await enroll([subjectId]);
    setEnrollingId(null);
  };

  const handleUnenroll = async (subjectId: string) => {
    setEnrollingId(subjectId);
    await unenroll(subjectId);
    setEnrollingId(null);
  };

  return (
    <main className="container py-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📚 My Subjects</h1>
          <p className="text-sm text-gray-500 mt-1">
            Enroll in subjects to access exam papers, practice, and AI tutoring.
          </p>
        </div>
        <select
          value={filterLevel}
          onChange={(e) => setFilterLevel(e.target.value)}
          className="input w-auto py-2 text-sm"
        >
          <option value="">All levels</option>
          {EDUCATION_LEVELS.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
        </div>
      ) : (
        <div className="space-y-8">
          {/* Enrolled Subjects */}
          {enrolledSubjects.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-gray-800 mb-4">
                ✅ Your Enrolled Subjects ({enrolledSubjects.length})
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {enrolledSubjects.map((subject) => (
                  <SubjectCard
                    key={subject.id}
                    subject={subject}
                    enrolled
                    loading={enrollingId === subject.id}
                    onUnenroll={() => handleUnenroll(subject.id)}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Available Subjects */}
          {availableSubjects.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold text-gray-800 mb-4">
                📋 Available Subjects ({availableSubjects.length})
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {availableSubjects.map((subject) => (
                  <SubjectCard
                    key={subject.id}
                    subject={subject}
                    enrolled={false}
                    loading={enrollingId === subject.id}
                    onEnroll={() => handleEnroll(subject.id)}
                  />
                ))}
              </div>
            </section>
          )}

          {subjects.length === 0 && (
            <div className="rounded-lg border bg-white p-12 text-center">
              <div className="text-4xl mb-3">📚</div>
              <p className="text-gray-600 font-medium">No subjects available yet</p>
              <p className="text-sm text-gray-400 mt-1">
                Ask your admin to set up subjects for your level.
              </p>
            </div>
          )}
        </div>
      )}
    </main>
  );
}

function SubjectCard({
  subject,
  enrolled,
  loading,
  onEnroll,
  onUnenroll,
}: {
  subject: SubjectRead;
  enrolled: boolean;
  loading: boolean;
  onEnroll?: () => void;
  onUnenroll?: () => void;
}) {
  return (
    <div className={`card flex flex-col gap-3 transition-all hover:shadow-md ${enrolled ? 'border-blue-200 bg-blue-50/30' : ''}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="text-3xl">{subject.icon || '📖'}</span>
          <div>
            <h3 className="font-semibold text-gray-900">{subject.name}</h3>
            <p className="text-xs text-gray-500">{subject.level} · {subject.document_count} docs</p>
          </div>
        </div>
        {enrolled && (
          <span className="shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700">
            Enrolled
          </span>
        )}
      </div>

      {subject.description && (
        <p className="text-sm text-gray-600 line-clamp-2">{subject.description}</p>
      )}

      <div className="mt-auto flex gap-2">
        {enrolled ? (
          <>
            <Link
              href={ROUTES.STUDENT_SUBJECT_DETAIL(subject.id)}
              className="flex-1 rounded-md bg-blue-600 px-3 py-2 text-center text-sm font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Open →
            </Link>
            <button
              onClick={onUnenroll}
              disabled={loading}
              className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors disabled:opacity-50"
            >
              {loading ? '...' : 'Leave'}
            </button>
          </>
        ) : (
          <button
            onClick={onEnroll}
            disabled={loading}
            className="flex-1 rounded-md border-2 border-blue-600 bg-white px-3 py-2 text-center text-sm font-medium text-blue-600 hover:bg-blue-50 transition-colors disabled:opacity-50"
          >
            {loading ? 'Enrolling...' : '+ Enroll'}
          </button>
        )}
      </div>
    </div>
  );
}
