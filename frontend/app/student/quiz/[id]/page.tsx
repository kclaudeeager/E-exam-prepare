'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/lib/hooks';
import { quizAPI, attemptAPI } from '@/lib/api';
import { QuizRead, AttemptRead } from '@/lib/types';
import { ROUTES } from '@/config/constants';

// ── Timer Component ─────────────────────────────────────────────────────────

function CountdownTimer({
  totalSeconds,
  onTimeUp,
}: {
  totalSeconds: number;
  onTimeUp: () => void;
}) {
  const [remaining, setRemaining] = useState(totalSeconds);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          onTimeUp();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [onTimeUp]);

  const hours = Math.floor(remaining / 3600);
  const minutes = Math.floor((remaining % 3600) / 60);
  const seconds = remaining % 60;

  const isLow = remaining <= 300; // 5 minutes warning
  const isCritical = remaining <= 60; // 1 minute warning

  return (
    <div
      className={`rounded-lg px-4 py-2 text-center font-mono text-lg font-bold ${
        isCritical
          ? 'animate-pulse bg-red-100 text-red-700'
          : isLow
            ? 'bg-yellow-100 text-yellow-700'
            : 'bg-blue-50 text-blue-700'
      }`}
    >
      <span className="text-xs font-normal uppercase tracking-wide">Time Left</span>
      <div className="text-2xl">
        {hours > 0 && `${hours.toString().padStart(2, '0')}:`}
        {minutes.toString().padStart(2, '0')}:{seconds.toString().padStart(2, '0')}
      </div>
    </div>
  );
}

// ── Results View ────────────────────────────────────────────────────────────

function ResultsView({
  result,
  quiz,
  onBack,
}: {
  result: AttemptRead;
  quiz: QuizRead;
  onBack: () => void;
}) {
  const router = useRouter();

  return (
    <div className="space-y-6">
      {/* Score Summary */}
      <div className="rounded-xl border bg-white p-8 text-center shadow-sm">
        <div
          className={`mx-auto mb-4 flex h-24 w-24 items-center justify-center rounded-full text-3xl font-bold text-white ${
            result.percentage >= 70
              ? 'bg-green-500'
              : result.percentage >= 50
                ? 'bg-yellow-500'
                : 'bg-red-500'
          }`}
        >
          {result.percentage.toFixed(0)}%
        </div>
        <p className="mb-1 text-sm font-medium uppercase tracking-wide text-blue-600">
          {quiz.mode === 'real-exam'
            ? '📝 Real Exam'
            : quiz.mode === 'adaptive'
              ? '🎯 Adaptive Practice'
              : '📚 Topic Practice'}
        </p>
        <h2 className="text-2xl font-bold text-gray-900">Quiz Complete!</h2>
        <p className="mt-2 text-gray-600">
          You got <span className="font-semibold">{result.score}</span> out of{' '}
          <span className="font-semibold">{result.total}</span> correct
        </p>
      </div>

      {/* Topic Breakdown */}
      {result.topic_breakdown.length > 0 && (
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <h3 className="mb-4 text-lg font-semibold text-gray-900">Topic Breakdown</h3>
          <div className="space-y-3">
            {result.topic_breakdown.map((ts) => (
              <div key={ts.topic} className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="font-medium text-gray-800">{ts.topic}</p>
                  <p className="text-sm text-gray-500">
                    {ts.correct}/{ts.total} correct
                  </p>
                </div>
                <div className="ml-4 flex items-center gap-3">
                  <div className="h-2 w-24 overflow-hidden rounded bg-gray-200">
                    <div
                      className={`h-full transition-all ${
                        ts.accuracy * 100 >= 70
                          ? 'bg-green-500'
                          : ts.accuracy * 100 >= 50
                            ? 'bg-yellow-500'
                            : 'bg-red-500'
                      }`}
                      style={{ width: `${ts.accuracy * 100}%` }}
                    />
                  </div>
                  <span
                    className={`text-sm font-bold ${
                      ts.accuracy * 100 >= 70
                        ? 'text-green-600'
                        : ts.accuracy * 100 >= 50
                          ? 'text-yellow-600'
                          : 'text-red-600'
                    }`}
                  >
                    {(ts.accuracy * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="flex-1 rounded-lg border border-gray-300 px-6 py-3 font-medium text-gray-700 hover:bg-gray-50"
        >
          ← Back to Practice
        </button>
        <button
          onClick={() => router.push(ROUTES.STUDENT_ATTEMPT_DETAIL(result.id))}
          className="flex-1 rounded-lg bg-purple-600 px-6 py-3 font-medium text-white hover:bg-purple-700"
        >
          🤖 Review with AI
        </button>
        <button
          onClick={() => router.push(ROUTES.STUDENT_PROGRESS)}
          className="flex-1 rounded-lg bg-blue-600 px-6 py-3 font-medium text-white hover:bg-blue-700"
        >
          View Progress
        </button>
      </div>
    </div>
  );
}

// ── Main Quiz Page ──────────────────────────────────────────────────────────

export default function QuizPage() {
  const router = useRouter();
  const params = useParams();
  const quizId = params.id as string;
  const { user } = useAuth();

  const [quiz, setQuiz] = useState<QuizRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Answer state: {question_id: answer_text}
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<AttemptRead | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  // Track if auto-submitted by timer
  const autoSubmittedRef = useRef(false);

  // Load quiz
  useEffect(() => {
    if (!quizId) return;
    (async () => {
      setLoading(true);
      try {
        const data = await quizAPI.get(quizId);
        setQuiz(data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load quiz');
      } finally {
        setLoading(false);
      }
    })();
  }, [quizId]);

  // Submit answers
  const handleSubmit = useCallback(async () => {
    if (!quiz || submitting || result) return;
    setSubmitting(true);
    setShowConfirm(false);

    try {
      const data = await attemptAPI.submit({
        quiz_id: quiz.id,
        answers,
      });
      setResult(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit quiz');
    } finally {
      setSubmitting(false);
    }
  }, [quiz, answers, submitting, result]);

  // Timer callback
  const handleTimeUp = useCallback(() => {
    if (!autoSubmittedRef.current && !result) {
      autoSubmittedRef.current = true;
      handleSubmit();
    }
  }, [handleSubmit, result]);

  const setAnswer = (questionId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  if (!user) {
    router.push(ROUTES.LOGIN);
    return null;
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
          <p className="text-gray-600">Loading quiz...</p>
        </div>
      </div>
    );
  }

  if (error && !quiz) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="rounded-xl border bg-white p-8 text-center shadow-sm">
          <p className="mb-4 text-red-600">{error}</p>
          <button
            onClick={() => router.push(ROUTES.STUDENT_PRACTICE)}
            className="rounded-lg bg-blue-600 px-6 py-2 text-white hover:bg-blue-700"
          >
            Back to Practice
          </button>
        </div>
      </div>
    );
  }

  if (!quiz) return null;

  // Show results if submitted
  if (result) {
    return (
      <>
        <header className="border-b bg-white shadow-sm">
          <div className="mx-auto max-w-3xl px-4 py-4">
            <h1 className="text-2xl font-bold text-gray-900">Quiz Results</h1>
          </div>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-8">
          <ResultsView
            result={result}
            quiz={quiz}
            onBack={() => router.push(ROUTES.STUDENT_PRACTICE)}
          />
        </main>
      </>
    );
  }

  const question = quiz.questions[currentIndex];
  const totalQuestions = quiz.questions.length;
  const answeredCount = Object.keys(answers).filter((k) => answers[k]?.trim()).length;
  const timerSeconds = (quiz.duration_minutes || totalQuestions * 2) * 60;

  return (
    <>
      {/* Sticky Header */}
      <header className="sticky top-0 z-10 border-b bg-white shadow-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
          <div>
            <h1 className="text-lg font-bold text-gray-900">
              {quiz.mode === 'real-exam'
                ? '📝 Real Exam'
                : quiz.mode === 'adaptive'
                  ? '🎯 Adaptive Practice'
                  : '📚 Topic Practice'}
            </h1>
            <p className="text-sm text-gray-500">
              {answeredCount}/{totalQuestions} answered
            </p>
          </div>
          <CountdownTimer totalSeconds={timerSeconds} onTimeUp={handleTimeUp} />
        </div>

        {/* Progress bar */}
        <div className="h-1 bg-gray-200">
          <div
            className="h-full bg-blue-600 transition-all duration-300"
            style={{ width: `${(answeredCount / totalQuestions) * 100}%` }}
          />
        </div>
      </header>

      {/* Instructions banner */}
      {quiz.instructions && currentIndex === 0 && (
        <div className="mx-auto max-w-3xl px-4 pt-4">
          <div className="rounded-lg bg-blue-50 p-4 text-sm text-blue-800">
            <strong>Instructions:</strong> {quiz.instructions}
          </div>
        </div>
      )}

      {/* Question */}
      <main className="mx-auto max-w-3xl px-4 py-6">
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
        )}

        <div className="rounded-xl border bg-white p-6 shadow-sm">
          {/* Question header */}
          <div className="mb-6 flex items-start gap-4">
            <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-700">
              {currentIndex + 1}
            </span>
            <div className="flex-1">
              <p className="text-lg text-gray-900">{question.text}</p>
              <div className="mt-2 flex gap-2">
                {question.topic && (
                  <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                    {question.topic}
                  </span>
                )}
                {question.difficulty && (
                  <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                    {question.difficulty}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Answer input */}
          <div className="ml-14">
            {question.options && question.options.length > 0 ? (
              // Multiple-choice
              <div className="space-y-3">
                {question.options.map((option, idx) => {
                  const letter = String.fromCharCode(65 + idx);
                  const isSelected = answers[question.id] === letter;
                  return (
                    <button
                      key={idx}
                      onClick={() => setAnswer(question.id, letter)}
                      className={`flex w-full items-center gap-3 rounded-lg border-2 p-4 text-left transition-colors ${
                        isSelected
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      <span
                        className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                          isSelected
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {letter}
                      </span>
                      <span className="text-gray-800">{option}</span>
                    </button>
                  );
                })}
              </div>
            ) : (
              // Short answer / essay
              <textarea
                value={answers[question.id] || ''}
                onChange={(e) => setAnswer(question.id, e.target.value)}
                placeholder="Type your answer here..."
                rows={4}
                className="w-full rounded-lg border-2 border-gray-200 p-4 text-gray-800 placeholder-gray-400 focus:border-blue-500 focus:outline-none"
              />
            )}
          </div>
        </div>

        {/* Navigation */}
        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
            disabled={currentIndex === 0}
            className="rounded-lg border border-gray-300 px-5 py-2.5 font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
          >
            ← Previous
          </button>

          {/* Question dots */}
          <div className="flex flex-wrap justify-center gap-1.5">
            {quiz.questions.map((q, idx) => {
              const isAnswered = !!answers[q.id]?.trim();
              const isCurrent = idx === currentIndex;
              return (
                <button
                  key={q.id}
                  onClick={() => setCurrentIndex(idx)}
                  className={`h-8 w-8 rounded-full text-xs font-medium transition-colors ${
                    isCurrent
                      ? 'bg-blue-600 text-white'
                      : isAnswered
                        ? 'bg-green-100 text-green-700 hover:bg-green-200'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                  title={`Question ${idx + 1}${isAnswered ? ' (answered)' : ''}`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>

          {currentIndex < totalQuestions - 1 ? (
            <button
              onClick={() => setCurrentIndex((i) => Math.min(totalQuestions - 1, i + 1))}
              className="rounded-lg bg-blue-600 px-5 py-2.5 font-medium text-white hover:bg-blue-700"
            >
              Next →
            </button>
          ) : (
            <button
              onClick={() => setShowConfirm(true)}
              className="rounded-lg bg-green-600 px-5 py-2.5 font-medium text-white hover:bg-green-700"
            >
              Submit Quiz
            </button>
          )}
        </div>

        {/* Floating submit (visible after scrolling through all questions) */}
        {answeredCount > 0 && (
          <div className="mt-4 text-center">
            <button
              onClick={() => setShowConfirm(true)}
              className="text-sm text-blue-600 underline hover:text-blue-800"
            >
              Submit quiz ({answeredCount}/{totalQuestions} answered)
            </button>
          </div>
        )}
      </main>

      {/* Confirmation Modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h3 className="text-lg font-bold text-gray-900">Submit Quiz?</h3>
            <p className="mt-2 text-gray-600">
              You have answered <strong>{answeredCount}</strong> of{' '}
              <strong>{totalQuestions}</strong> questions.
              {answeredCount < totalQuestions && (
                <span className="mt-1 block text-yellow-600">
                  ⚠️ {totalQuestions - answeredCount} question(s) are unanswered.
                </span>
              )}
            </p>
            <div className="mt-6 flex gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 rounded-lg border border-gray-300 px-4 py-2.5 font-medium text-gray-700 hover:bg-gray-50"
              >
                Continue Quiz
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="flex-1 rounded-lg bg-green-600 px-4 py-2.5 font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                {submitting ? 'Submitting...' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
