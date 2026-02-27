'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks';
import { documentAPI } from '@/lib/api';
import { DocumentRead } from '@/lib/types';
import { ROUTES, EDUCATION_LEVELS } from '@/config/constants';

const LEVEL_LABELS: Record<string, string> = Object.fromEntries(
  EDUCATION_LEVELS.map(({ value, label }) => [value, label]),
);

export default function BrowseExamsPage() {
  const router = useRouter();
  const { user, isAuthenticated, fetchCurrentUser } = useAuth();

  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [filterSubject, setFilterSubject] = useState('');
  const [filterLevel, setFilterLevel] = useState('');

  useEffect(() => {
    const init = async () => {
      if (!isAuthenticated) {
        await fetchCurrentUser();
      }
      setLoading(false);
    };
    init();
  }, [isAuthenticated, fetchCurrentUser]);

  useEffect(() => {
    if (!user) return;
    if (user.role !== 'student') {
      router.push(ROUTES.DASHBOARD);
      return;
    }
    loadDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const loadDocuments = async () => {
    setLoading(true);
    setError('');
    try {
      const docs = await documentAPI.list(
        filterSubject || undefined,
        filterLevel || undefined,
      );
      // Only show fully ingested docs — archived are already excluded by the backend
      setDocuments(docs.filter((d) => d.ingestion_status === 'completed'));
    } catch {
      setError('Failed to load exam papers. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleFilter = (e: React.FormEvent) => {
    e.preventDefault();
    loadDocuments();
  };

  const handleAskAI = (doc: DocumentRead) => {
    // Prefer the stored collection_name; fall back to derived pattern
    const collection = doc.collection_name || `${doc.level}_${doc.subject}`.replace(/ /g, '_');
    const params = new URLSearchParams({
      subject: doc.subject,
      level: doc.level,
      collection,
    });
    router.push(`${ROUTES.STUDENT_ASK_AI}?${params.toString()}`);
  };

  if (loading && !documents.length) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading exam papers…</p>
      </div>
    );
  }

  return (
    <>
      <main className="container py-8">
        <div className="mb-6 flex flex-col gap-1">
          <h1 className="text-2xl font-bold text-gray-900">Exam Papers</h1>
          <p className="text-sm text-gray-500">
            Browse past exam papers uploaded by your teachers. Use <strong>Ask AI</strong> to get explanations for any paper.
          </p>
        </div>

        {/* Filters */}
        <form
          onSubmit={handleFilter}
          className="mb-6 flex flex-wrap gap-3 rounded-lg border bg-white p-4 shadow-sm"
        >
          <div className="flex flex-1 flex-col gap-1 min-w-[160px]">
            <label className="text-xs font-medium text-gray-600">Subject</label>
            <input
              type="text"
              value={filterSubject}
              onChange={(e) => setFilterSubject(e.target.value)}
              placeholder="e.g. Mathematics"
              className="input"
            />
          </div>
          <div className="flex flex-1 flex-col gap-1 min-w-[160px]">
            <label className="text-xs font-medium text-gray-600">Level</label>
            <select
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
              className="input"
            >
              <option value="">All levels</option>
              {EDUCATION_LEVELS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button type="submit" className="btn-primary px-4 py-2">
              Filter
            </button>
          </div>
        </form>

        {error && (
          <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Document grid */}
        {documents.length === 0 ? (
          <div className="rounded-lg border bg-white p-12 text-center">
            <div className="text-4xl mb-3">📄</div>
            <p className="text-gray-600 font-medium">No exam papers found</p>
            <p className="text-sm text-gray-400 mt-1">
              {filterSubject || filterLevel
                ? 'Try clearing the filters.'
                : 'Your teacher has not uploaded any papers yet.'}
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {documents.map((doc) => {
              // Clean up filename for display: strip extension, replace separators
              const displayName = doc.filename
                .replace(/\.pdf$/i, '')
                .replace(/[_-]+/g, ' ')
                .replace(/\s+/g, ' ')
                .trim();
              const hasDuplicateSubject =
                documents.filter((d) => d.subject === doc.subject && d.level === doc.level).length > 1;

              return (
              <div key={doc.id} className="card flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h3 className="font-semibold text-gray-900 truncate" title={displayName}>
                      {hasDuplicateSubject ? displayName : doc.subject}
                    </h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {hasDuplicateSubject && <span className="text-gray-600">{doc.subject} · </span>}
                      {LEVEL_LABELS[doc.level] ?? doc.level} · {doc.year}
                    </p>
                    {doc.page_count && (
                      <p className="text-xs text-gray-400 mt-0.5">📄 {doc.page_count} pages</p>
                    )}
                  </div>
                  <span className="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                    {doc.level}
                  </span>
                </div>

                {doc.official_duration_minutes && (
                  <p className="text-xs text-gray-500">
                    ⏱ {Math.floor(doc.official_duration_minutes / 60)}h{' '}
                    {doc.official_duration_minutes % 60 > 0
                      ? `${doc.official_duration_minutes % 60}min`
                      : ''}{' '}
                    duration
                  </p>
                )}

                <div className="mt-auto flex gap-2">
                  <button
                    onClick={() => handleAskAI(doc)}
                    className="flex-1 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors text-center"
                  >
                    🤖 Ask AI
                  </button>
                  <Link
                    href={`${ROUTES.STUDENT_PRACTICE}?subject=${encodeURIComponent(doc.subject)}&level=${doc.level}`}
                    className="flex-1 rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors text-center"
                  >
                    Practice
                  </Link>
                </div>
              </div>
              );
            })}
          </div>
        )}
      </main>
    </>
  );
}
