'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth, useQuiz } from '@/lib/hooks';
import { QUIZ_MODES, ROUTES } from '@/config/constants';
import { QuizMode } from '@/lib/types';

export default function PracticePage() {
  const router = useRouter();
  const { user } = useAuth();
  const { generate } = useQuiz();
  const [loadingMode, setLoadingMode] = useState<QuizMode | null>(null);
  const [error, setError] = useState('');

  if (!user) {
    router.push(ROUTES.LOGIN);
    return null;
  }

  const handleStartQuiz = async (mode: QuizMode) => {
    setLoadingMode(mode);
    setError('');

    const result = await generate({
      mode,
      count: mode === 'real-exam' ? undefined : 10,
    });

    setLoadingMode(null);

    if (!result.success || !result.data) {
      setError(result.error || 'Failed to generate quiz');
      return;
    }

    // Navigate to quiz page with quiz ID
    router.push(`/student/quiz/${result.data.id}`);
  };

  return (
    <main className="container py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Practice Quizzes</h1>
      <div className="space-y-6">
        {error && (
          <div className="rounded bg-red-50 p-4 text-red-700">
            {error}
          </div>
        )}

        <div className="space-y-4">
          {QUIZ_MODES.map((modeOption) => {
            const isThis = loadingMode === modeOption.value;
            const isAny = loadingMode !== null;
            return (
              <div
                key={modeOption.value}
                className={`card cursor-pointer hover:shadow-md ${
                  isAny && !isThis ? 'opacity-50 pointer-events-none' : ''
                }`}
                onClick={() => !isAny && handleStartQuiz(modeOption.value)}
              >
                <div className="flex-between">
                  <div>
                    <h3 className="font-semibold text-gray-900">{modeOption.label}</h3>
                    <p className="text-sm text-gray-600">{modeOption.description}</p>
                  </div>
                  <button
                    disabled={isAny}
                    className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {isThis ? 'Loading...' : 'Start'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
