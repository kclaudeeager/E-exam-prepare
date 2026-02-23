'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import { useAuth } from '@/lib/hooks';
import { attemptAPI } from '@/lib/api';
import { AttemptDetailRead, AttemptAnswerRead, AIReviewResponse } from '@/lib/types';
import { ROUTES } from '@/config/constants';

// ── AI Explanation Panel ─────────────────────────────────────────────────────

function AIPanel({
  title,
  loading,
  explanation,
  onAsk,
  onClose,
}: {
  title: string;
  loading: boolean;
  explanation: AIReviewResponse | null;
  onAsk: (question: string) => void;
  onClose: () => void;
}) {
  const [input, setInput] = useState('');
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [explanation, loading]);

  return (
    <div ref={panelRef} className="mt-4 rounded-xl border-2 border-purple-200 bg-purple-50/50 p-5">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="flex items-center gap-2 font-semibold text-purple-900">
          <span className="text-lg">🤖</span> {title}
        </h4>
        <button
          onClick={onClose}
          className="rounded-full p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
          title="Close"
        >
          ✕
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-6">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-purple-300 border-t-purple-600" />
          <span className="text-sm text-purple-700">AI is analyzing...</span>
        </div>
      )}

      {explanation && !loading && (
        <div className="prose prose-sm max-w-none prose-headings:text-purple-900 prose-strong:text-gray-900 prose-li:text-gray-700">
          <ReactMarkdown>{explanation.explanation}</ReactMarkdown>
          {explanation.sources && explanation.sources.length > 0 && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs text-purple-600 hover:text-purple-800">
                📚 View {explanation.sources.length} source(s)
              </summary>
              <div className="mt-2 space-y-2">
                {explanation.sources.map((src, i) => (
                  <div key={i} className="rounded bg-white/70 p-2 text-xs text-gray-600">
                    {src.content?.slice(0, 200)}...
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {/* Follow-up question input */}
      <div className="mt-4 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && input.trim()) {
              onAsk(input.trim());
              setInput('');
            }
          }}
          placeholder="Ask a follow-up question..."
          className="flex-1 rounded-lg border border-purple-200 bg-white px-3 py-2 text-sm placeholder-gray-400 focus:border-purple-400 focus:outline-none"
        />
        <button
          onClick={() => {
            if (input.trim()) {
              onAsk(input.trim());
              setInput('');
            }
          }}
          disabled={loading || !input.trim()}
          className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
        >
          Ask
        </button>
      </div>
    </div>
  );
}

// ── Question Card ────────────────────────────────────────────────────────────

function QuestionCard({
  index,
  ans,
  attemptId,
}: {
  index: number;
  ans: AttemptAnswerRead;
  attemptId: string;
}) {
  const [showAI, setShowAI] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<AIReviewResponse | null>(null);

  const handleAskAI = async (question?: string) => {
    setShowAI(true);
    setAiLoading(true);
    try {
      const data = await attemptAPI.explainQuestion(attemptId, ans.question_id, question);
      setAiResult(data);
    } catch {
      setAiResult({
        explanation: 'Sorry, AI review is currently unavailable. Please try again later.',
        sources: [],
      });
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div
      className={`rounded-xl border-2 p-5 transition-all ${
        ans.is_correct === true
          ? 'border-green-200 bg-green-50/50'
          : ans.is_correct === false
            ? 'border-red-200 bg-red-50/50'
            : 'border-gray-200 bg-gray-50/50'
      }`}
    >
      {/* Question header */}
      <div className="mb-4 flex items-start gap-3">
        <span
          className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${
            ans.is_correct === true
              ? 'bg-green-500'
              : ans.is_correct === false
                ? 'bg-red-500'
                : 'bg-gray-400'
          }`}
        >
          {ans.is_correct === true ? '✓' : ans.is_correct === false ? '✗' : '?'}
        </span>
        <div className="flex-1">
          <p className="font-medium text-gray-900">
            <span className="text-gray-500">Q{index}.</span> {ans.question_text}
          </p>
          <div className="mt-1 flex flex-wrap gap-2">
            {ans.topic && (
              <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                {ans.topic}
              </span>
            )}
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                ans.is_correct
                  ? 'bg-green-100 text-green-700'
                  : 'bg-red-100 text-red-700'
              }`}
            >
              {ans.is_correct ? 'Correct' : 'Incorrect'}
            </span>
          </div>
        </div>
      </div>

      {/* MCQ options display */}
      {ans.options && ans.options.length > 0 && (
        <div className="mb-4 ml-11 space-y-1.5">
          {ans.options.map((opt, i) => {
            const letter = String.fromCharCode(65 + i);
            const isStudentChoice = ans.student_answer?.toUpperCase() === letter;
            const isCorrectOption = ans.correct_answer?.toUpperCase() === letter;
            return (
              <div
                key={i}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm ${
                  isCorrectOption
                    ? 'bg-green-100 font-medium text-green-800 ring-1 ring-green-300'
                    : isStudentChoice && !isCorrectOption
                      ? 'bg-red-100 text-red-700 line-through ring-1 ring-red-300'
                      : 'bg-white/60 text-gray-600'
                }`}
              >
                <span
                  className={`flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    isCorrectOption
                      ? 'bg-green-500 text-white'
                      : isStudentChoice && !isCorrectOption
                        ? 'bg-red-400 text-white'
                        : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  {letter}
                </span>
                <span>{opt}</span>
                {isCorrectOption && <span className="ml-auto text-green-600">✓ Correct</span>}
                {isStudentChoice && !isCorrectOption && (
                  <span className="ml-auto text-xs text-red-500">Your answer</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Short answer display */}
      {!ans.options && (
        <div className="mb-4 ml-11 space-y-2">
          <div className="rounded-lg bg-white/70 p-3 text-sm ring-1 ring-gray-200">
            <span className="text-gray-500">Your answer: </span>
            <span className={`font-medium ${ans.is_correct ? 'text-green-700' : 'text-red-700'}`}>
              {ans.student_answer || <em className="text-gray-400">Not answered</em>}
            </span>
          </div>
          {ans.correct_answer && !ans.is_correct && (
            <div className="rounded-lg bg-green-50 p-3 text-sm ring-1 ring-green-200">
              <span className="text-gray-500">Correct answer: </span>
              <span className="font-medium text-green-700">{ans.correct_answer}</span>
            </div>
          )}
        </div>
      )}

      {/* Ask AI button */}
      {!showAI && (
        <div className="ml-11">
          <button
            onClick={() => handleAskAI()}
            className="flex items-center gap-2 rounded-lg border border-purple-200 bg-white px-4 py-2 text-sm font-medium text-purple-700 transition-colors hover:bg-purple-50 hover:border-purple-300"
          >
            <span>🤖</span>
            {ans.is_correct ? 'Learn more about this' : 'Explain this to me'}
          </button>
        </div>
      )}

      {/* AI Panel */}
      {showAI && (
        <AIPanel
          title={`AI Explanation — Q${index}`}
          loading={aiLoading}
          explanation={aiResult}
          onAsk={(q) => handleAskAI(q)}
          onClose={() => {
            setShowAI(false);
            setAiResult(null);
          }}
        />
      )}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────

export default function AttemptDetailPage() {
  const router = useRouter();
  const params = useParams();
  const attemptId = params.id as string;
  const { user } = useAuth();

  const [attempt, setAttempt] = useState<AttemptDetailRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Full attempt AI review state
  const [showFullReview, setShowFullReview] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewResult, setReviewResult] = useState<AIReviewResponse | null>(null);

  // Filter state
  const [filter, setFilter] = useState<'all' | 'correct' | 'wrong'>('all');

  useEffect(() => {
    if (!attemptId) return;
    (async () => {
      setLoading(true);
      try {
        const data = await attemptAPI.get(attemptId);
        setAttempt(data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load attempt');
      } finally {
        setLoading(false);
      }
    })();
  }, [attemptId]);

  const handleFullReview = async (question?: string) => {
    setShowFullReview(true);
    setReviewLoading(true);
    try {
      const data = await attemptAPI.reviewWithAI(attemptId, question);
      setReviewResult(data);
    } catch {
      setReviewResult({
        explanation: 'Sorry, AI review is currently unavailable. Please try again later.',
        sources: [],
      });
    } finally {
      setReviewLoading(false);
    }
  };

  if (!user) {
    router.push(ROUTES.LOGIN);
    return null;
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
          <p className="text-gray-600">Loading attempt...</p>
        </div>
      </div>
    );
  }

  if (error || !attempt) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="rounded-xl border bg-white p-8 text-center shadow-sm">
          <p className="mb-4 text-red-600">{error || 'Attempt not found'}</p>
          <button
            onClick={() => router.push(ROUTES.STUDENT_ATTEMPTS)}
            className="rounded-lg bg-blue-600 px-6 py-2 text-white hover:bg-blue-700"
          >
            Back to Attempts
          </button>
        </div>
      </div>
    );
  }

  const wrongCount = attempt.answers.filter((a) => !a.is_correct).length;
  const correctCount = attempt.answers.filter((a) => a.is_correct).length;

  const filteredAnswers =
    filter === 'all'
      ? attempt.answers
      : filter === 'correct'
        ? attempt.answers.filter((a) => a.is_correct)
        : attempt.answers.filter((a) => !a.is_correct);

  return (
    <>
      {/* Header */}
      <header className="border-b bg-white shadow-sm">
        <div className="mx-auto max-w-4xl px-4 py-4">
          <button
            onClick={() => router.push(ROUTES.STUDENT_ATTEMPTS)}
            className="mb-2 text-sm text-blue-600 hover:underline"
          >
            ← Back to Attempts
          </button>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Attempt Review</h1>
              <p className="text-sm text-gray-500">
                Submitted {attempt.submitted_at ? new Date(attempt.submitted_at).toLocaleString() : 'N/A'}
              </p>
            </div>
            <button
              onClick={() => handleFullReview()}
              className="flex items-center gap-2 rounded-lg bg-purple-600 px-5 py-2.5 font-medium text-white shadow-sm transition-colors hover:bg-purple-700"
            >
              <span>🤖</span> Review with AI
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8 space-y-6">
        {/* Score Summary */}
        <div className="rounded-xl border bg-white p-6 shadow-sm">
          <div className="flex items-center gap-6">
            <div
              className={`flex h-20 w-20 flex-shrink-0 items-center justify-center rounded-full text-2xl font-bold text-white ${
                attempt.percentage >= 70
                  ? 'bg-green-500'
                  : attempt.percentage >= 50
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
              }`}
            >
              {attempt.percentage.toFixed(0)}%
            </div>
            <div className="flex-1">
              <p className="text-2xl font-bold text-gray-900">
                {attempt.score}/{attempt.total}
              </p>
              <p className="text-gray-600">questions correct</p>
              <div className="mt-2 flex gap-4 text-sm">
                <span className="text-green-600">✓ {correctCount} correct</span>
                <span className="text-red-600">✗ {wrongCount} wrong</span>
              </div>
            </div>
          </div>
        </div>

        {/* Full AI Review Panel */}
        {showFullReview && (
          <AIPanel
            title="Full Attempt Review"
            loading={reviewLoading}
            explanation={reviewResult}
            onAsk={(q) => handleFullReview(q)}
            onClose={() => {
              setShowFullReview(false);
              setReviewResult(null);
            }}
          />
        )}

        {/* Topic Breakdown */}
        {attempt.topic_breakdown.length > 0 && (
          <div className="rounded-xl border bg-white p-6 shadow-sm">
            <h3 className="mb-4 text-lg font-semibold text-gray-900">
              Topic Breakdown
            </h3>
            <div className="space-y-3">
              {attempt.topic_breakdown.map((ts) => (
                <div key={ts.topic} className="flex items-center justify-between">
                  <div className="flex-1">
                    <p className="font-medium text-gray-800">{ts.topic}</p>
                    <p className="text-sm text-gray-500">
                      {ts.correct}/{ts.total} correct
                    </p>
                  </div>
                  <div className="ml-4 flex items-center gap-3">
                    <div className="h-2.5 w-28 overflow-hidden rounded-full bg-gray-200">
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
                      className={`w-10 text-right text-sm font-bold ${
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

        {/* Question Review Section */}
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">
              Question Review
            </h3>
            {/* Filter tabs */}
            <div className="flex rounded-lg border bg-white p-1 shadow-sm">
              {([
                { key: 'all', label: `All (${attempt.answers.length})` },
                { key: 'wrong', label: `Wrong (${wrongCount})` },
                { key: 'correct', label: `Correct (${correctCount})` },
              ] as const).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setFilter(tab.key)}
                  className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                    filter === tab.key
                      ? 'bg-blue-600 text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {filteredAnswers.length === 0 ? (
            <div className="rounded-xl border bg-white p-8 text-center shadow-sm">
              <p className="text-gray-500">
                {filter === 'wrong'
                  ? '🎉 No wrong answers — great job!'
                  : 'No questions match this filter.'}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredAnswers.map((ans) => {
                const originalIndex =
                  attempt.answers.findIndex(
                    (a) => a.question_id === ans.question_id
                  ) + 1;
                return (
                  <QuestionCard
                    key={ans.question_id}
                    index={originalIndex}
                    ans={ans}
                    attemptId={attemptId}
                  />
                );
              })}
            </div>
          )}
        </div>

        {/* Bottom Actions */}
        <div className="flex gap-3 pb-8">
          <button
            onClick={() => router.push(ROUTES.STUDENT_ATTEMPTS)}
            className="flex-1 rounded-lg border border-gray-300 px-6 py-3 font-medium text-gray-700 hover:bg-gray-50"
          >
            ← All Attempts
          </button>
          <button
            onClick={() => !showFullReview && handleFullReview()}
            disabled={showFullReview && reviewLoading}
            className="flex-1 rounded-lg bg-purple-600 px-6 py-3 font-medium text-white hover:bg-purple-700 disabled:opacity-50"
          >
            🤖 {showFullReview ? 'AI Review Open ↑' : 'Review with AI'}
          </button>
          <button
            onClick={() => router.push(ROUTES.STUDENT_PRACTICE)}
            className="flex-1 rounded-lg bg-blue-600 px-6 py-3 font-medium text-white hover:bg-blue-700"
          >
            Practice Again
          </button>
        </div>
      </main>
    </>
  );
}
