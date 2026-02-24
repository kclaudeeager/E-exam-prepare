'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/hooks';
import { documentAPI, quizAPI } from '@/lib/api';
import { QUIZ_MODES, ROUTES, EDUCATION_LEVELS } from '@/config/constants';
import { DocumentRead, QuizMode } from '@/lib/types';

export default function PracticePage() {
  const router = useRouter();
  const { user } = useAuth();

  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [selectedDoc, setSelectedDoc] = useState<DocumentRead | null>(null);
  const [loadingMode, setLoadingMode] = useState<QuizMode | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) {
      router.push(ROUTES.LOGIN);
      return;
    }
    documentAPI
      .list()
      .then((docs) => setDocuments(docs.filter((d) => d.ingestion_status === 'completed')))
      .catch(() => setError('Failed to load exam papers'))
      .finally(() => setLoadingDocs(false));
  }, [user, router]);

  if (!user) {
    return null;
  }

  const handleStartQuiz = async (mode: QuizMode) => {
    if (!selectedDoc) return;
    setLoadingMode(mode);
    setError('');
    try {
      const quiz = await quizAPI.generate({
        mode,
        document_id: selectedDoc.id,
        subject: selectedDoc.subject,
        count: mode === 'real-exam' ? undefined : 10,
      });
      router.push(`/student/quiz/${quiz.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate quiz');
      setLoadingMode(null);
    }
  };

  const levelLabel = (val: string) =>
    EDUCATION_LEVELS.find((l) => l.value === val)?.label ?? val;

  return (
    <main className="container py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Practice Quizzes</h1>
        <p className="mt-1 text-gray-600">
          {selectedDoc ? 'Choose a quiz mode to start practicing' : 'Select an exam paper to practice from'}
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      )}

      {!selectedDoc ? (
        /* ── Step 1: Select exam paper ── */
        loadingDocs ? (
          <div className="flex items-center justify-center py-20">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
          </div>
        ) : documents.length === 0 ? (
          <div className="card py-12 text-center">
            <p className="text-2xl">📚</p>
            <p className="mt-2 font-medium text-gray-700">No exam papers available yet</p>
            <p className="mt-1 text-sm text-gray-500">
              Ask your admin to upload papers for your level.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <button
                key={doc.id}
                onClick={() => { setSelectedDoc(doc); setError(''); }}
                className="card w-full cursor-pointer text-left transition-all hover:border-blue-300 hover:shadow-md"
              >
                <div className="flex items-center gap-4">
                  <div className="flex-shrink-0 text-3xl">📄</div>
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate font-semibold text-gray-900">{doc.filename}</h3>
                    <p className="text-sm text-gray-600">
                      {doc.subject} · {levelLabel(doc.level)} · {doc.year}
                    </p>
                    {doc.official_duration_minutes && (
                      <p className="text-xs text-gray-400">
                        ⏱ {doc.official_duration_minutes} min official duration
                      </p>
                    )}
                  </div>
                  <div className="flex flex-shrink-0 gap-2">
                    {doc.is_personal && (
                      <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
                        Personal
                      </span>
                    )}
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                      {doc.level}
                    </span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )
      ) : (
        /* ── Step 2: Choose quiz mode ── */
        <div className="space-y-6">
          {/* Selected paper banner */}
          <div className="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4">
            <span className="text-2xl">📄</span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">
                Selected Paper
              </p>
              <p className="truncate font-semibold text-gray-900">{selectedDoc.filename}</p>
              <p className="text-sm text-gray-600">
                {selectedDoc.subject} · {levelLabel(selectedDoc.level)} · {selectedDoc.year}
              </p>
            </div>
            <button
              onClick={() => { setSelectedDoc(null); setError(''); setLoadingMode(null); }}
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Change
            </button>
          </div>

          {/* Quiz mode options */}
          <div className="space-y-4">
            {QUIZ_MODES.map((modeOption) => {
              const isThis = loadingMode === modeOption.value;
              const isAny = loadingMode !== null;
              return (
                <div
                  key={modeOption.value}
                  className={`card cursor-pointer transition-all hover:shadow-md ${
                    isAny && !isThis ? 'pointer-events-none opacity-50' : ''
                  }`}
                  onClick={() => !isAny && handleStartQuiz(modeOption.value as QuizMode)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">{modeOption.label}</h3>
                      <p className="text-sm text-gray-600">{modeOption.description}</p>
                    </div>
                    <button
                      disabled={isAny}
                      className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {isThis ? 'Loading…' : 'Start'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </main>
  );
}
