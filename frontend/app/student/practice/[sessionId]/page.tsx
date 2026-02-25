'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks';
import { practiceAPI, subjectAPI } from '@/lib/api';
import {
  PracticeQuestionRead,
  PracticeAnswerResult,
  PracticeSessionDetail,
  SourceReference,
  SubjectRead,
} from '@/lib/types';
import { ROUTES } from '@/config/constants';
import PDFViewerModal from '@/components/PDFViewerModal';

type Phase = 'loading' | 'answering' | 'grading' | 'graded' | 'completed' | 'error';

export default function PracticeSessionPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const sessionId = params.sessionId as string;

  const [phase, setPhase] = useState<Phase>('loading');
  const [question, setQuestion] = useState<PracticeQuestionRead | null>(null);
  const [answer, setAnswer] = useState('');
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [gradingResult, setGradingResult] = useState<PracticeAnswerResult | null>(null);
  const [sessionResult, setSessionResult] = useState<PracticeSessionDetail | null>(null);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [error, setError] = useState('');
  const [showSources, setShowSources] = useState(false);

  // Subject info for display
  const [subjectInfo, setSubjectInfo] = useState<SubjectRead | null>(null);

  // Timer
  const [startTime] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);

  // PDF viewer state for clickable source references
  const [viewingSource, setViewingSource] = useState<{
    documentId: string;
    documentName: string;
    page?: number;
  } | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const loadNextQuestion = useCallback(async () => {
    setPhase('loading');
    setError('');
    setAnswer('');
    setImageBase64(null);
    setImagePreview(null);
    setGradingResult(null);
    setShowSources(false);
    try {
      const q = await practiceAPI.getNextQuestion(sessionId);
      if (!q) {
        // Backend returned null — session is complete
        await loadSessionResults();
        return;
      }
      setQuestion(q);
      setTotalQuestions(q.total_questions);
      setPhase('answering');
      // Focus textarea after load
      setTimeout(() => textareaRef.current?.focus(), 100);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const status = err?.response?.status;
      if (status === 404 || detail?.includes('All questions answered') || detail?.includes('session complete')) {
        // Session complete, load results
        await loadSessionResults();
      } else {
        setError(detail || 'Failed to load question');
        setPhase('error');
      }
    }
  }, [sessionId]);

  // Load subject info once we have a session result or first question
  const loadSubjectInfo = useCallback(async (subjectId: string) => {
    try {
      const subjects = await subjectAPI.list();
      const match = subjects.find((s) => s.id === subjectId);
      if (match) setSubjectInfo(match);
    } catch { /* ignore */ }
  }, []);

  const loadSessionResults = useCallback(async () => {
    try {
      const result = await practiceAPI.get(sessionId);
      setSessionResult(result);
      if (result.subject_id && !subjectInfo) {
        loadSubjectInfo(result.subject_id);
      }
      setPhase('completed');
    } catch {
      setError('Failed to load session results');
      setPhase('error');
    }
  }, [sessionId, subjectInfo, loadSubjectInfo]);

  useEffect(() => {
    if (user) loadNextQuestion();
  }, [user, loadNextQuestion]);

  // Timer effect
  useEffect(() => {
    if (phase === 'completed') return;
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [startTime, phase]);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Preview
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = (reader.result as string).split(',')[1];
      setImageBase64(base64);
      setImagePreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  const handleSubmitAnswer = async () => {
    if (!question && !answer && !imageBase64) return;
    setPhase('grading');
    setError('');

    try {
      const result = await practiceAPI.submitAnswer(sessionId, {
        question_id: question?.id,
        question_text: question?.text,
        answer_text: answer || undefined,
        answer_image_base64: imageBase64 || undefined,
      });
      setGradingResult(result);
      setAnsweredCount((prev) => prev + 1);
      if (result.is_correct) setCorrectCount((prev) => prev + 1);
      setPhase('graded');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to grade answer');
      setPhase('answering');
    }
  };

  const handleComplete = async () => {
    try {
      await practiceAPI.complete(sessionId);
      // complete() returns PracticeSessionRead (no answers), so
      // load the full detail with answers for the results view
      await loadSessionResults();
    } catch {
      await loadSessionResults();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && e.metaKey) {
      e.preventDefault();
      handleSubmitAnswer();
    }
  };

  if (!user) return null;

  // Format elapsed time
  const fmtTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <main className="container max-w-3xl py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link href={subjectInfo ? `/student/subjects/${subjectInfo.id}?tab=practice` : ROUTES.STUDENT_SUBJECTS} className="text-sm text-gray-500 hover:text-blue-600 transition-colors">
            ← {subjectInfo ? subjectInfo.name : 'Back to Subjects'}
          </Link>
          <h1 className="text-xl font-bold text-gray-900 mt-1">
            ✏️ Practice Mode
            {subjectInfo && (
              <span className="ml-2 text-base font-normal text-gray-500">
                {subjectInfo.icon || '📚'} {subjectInfo.name}
              </span>
            )}
          </h1>
        </div>
        {phase !== 'completed' && totalQuestions > 0 && (
          <div className="text-right space-y-1">
            <div className="flex items-center gap-3 justify-end">
              <span className="text-xs text-gray-400">⏱ {fmtTime(elapsed)}</span>
              <span className="text-sm font-medium text-gray-700">
                {answeredCount}/{totalQuestions}
              </span>
            </div>
            <div className="w-32 h-2 bg-gray-200 rounded-full">
              <div
                className="h-2 bg-blue-600 rounded-full transition-all"
                style={{ width: `${(answeredCount / totalQuestions) * 100}%` }}
              />
            </div>
            {answeredCount > 0 && (
              <p className="text-xs text-gray-400">
                {correctCount}/{answeredCount} correct · {Math.round((correctCount / answeredCount) * 100)}%
              </p>
            )}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
          {error}
          <button onClick={loadNextQuestion} className="ml-2 underline">Retry</button>
        </div>
      )}

      {/* Loading */}
      {phase === 'loading' && (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
          <p className="text-sm text-gray-500">Loading question...</p>
        </div>
      )}

      {/* Answering Phase */}
      {phase === 'answering' && question && (
        <div className="space-y-6">
          {/* Question card */}
          <div className="rounded-xl border-2 border-blue-100 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <span className="rounded-full bg-blue-100 px-3 py-0.5 text-sm font-semibold text-blue-700">
                Q{question.question_number} of {question.total_questions}
              </span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                question.question_type === 'multiple-choice' ? 'bg-purple-100 text-purple-700'
                : question.question_type === 'true-or-false' ? 'bg-amber-100 text-amber-700'
                : question.question_type === 'fill-in-the-blank' ? 'bg-cyan-100 text-cyan-700'
                : 'bg-gray-100 text-gray-600'
              }`}>
                {question.question_type === 'multiple-choice' ? '🔘 MCQ'
                  : question.question_type === 'true-or-false' ? '✓✗ True/False'
                  : question.question_type === 'fill-in-the-blank' ? '✏️ Fill in blank'
                  : '📝 Short answer'}
              </span>
              {question.topic && (
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                  📂 {question.topic}
                </span>
              )}
              {question.difficulty && (
                <span className={`rounded-full px-2 py-0.5 text-xs ${
                  question.difficulty === 'easy' ? 'bg-green-100 text-green-700'
                  : question.difficulty === 'hard' ? 'bg-red-100 text-red-700'
                  : 'bg-yellow-100 text-yellow-700'
                }`}>
                  {question.difficulty === 'easy' ? '🟢' : question.difficulty === 'hard' ? '🔴' : '🟡'} {question.difficulty}
                </span>
              )}
            </div>
            <p className="text-gray-900 leading-relaxed whitespace-pre-wrap text-base">{question.text}</p>

            {/* Source reference links — helps students see diagrams/figures */}
            {question.source_references && question.source_references.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {question.source_references.filter(s => s.document_id).map((src, i) => (
                  <button
                    key={i}
                    onClick={() => setViewingSource({
                      documentId: src.document_id!,
                      documentName: src.document_name || 'Source Document',
                      page: src.page_number ?? undefined,
                    })}
                    className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
                    title={src.content_snippet || 'View source document'}
                  >
                    📄 {src.page_number ? `View page ${src.page_number}` : 'View source'}
                    {src.document_name && (
                      <span className="text-blue-500 ml-1 max-w-[120px] truncate">
                        — {src.document_name}
                      </span>
                    )}
                  </button>
                ))}
                <span className="self-center text-[10px] text-gray-400 italic">
                  Open source document if the question references a diagram or figure
                </span>
              </div>
            )}

            {/* MCQ options */}
            {question.options && question.options.length > 0 && (
              <div className="mt-4 space-y-2">
                {question.options.map((opt, i) => (
                  <button
                    key={i}
                    onClick={() => setAnswer(opt)}
                    className={`w-full text-left rounded-lg border px-4 py-2.5 text-sm transition-colors ${
                      answer === opt
                        ? 'border-blue-500 bg-blue-50 text-blue-700 font-medium'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <span className="font-medium mr-2">{String.fromCharCode(65 + i)}.</span>
                    {opt}
                  </button>
                ))}
              </div>
            )}

            {/* True/False buttons */}
            {question.question_type === 'true-or-false' && (!question.options || question.options.length === 0) && (
              <div className="mt-4 grid grid-cols-2 gap-3">
                {['True', 'False'].map((val) => (
                  <button
                    key={val}
                    onClick={() => setAnswer(val)}
                    className={`rounded-lg border-2 px-6 py-3 text-sm font-medium transition-all ${
                      answer === val
                        ? val === 'True'
                          ? 'border-green-500 bg-green-50 text-green-700'
                          : 'border-red-500 bg-red-50 text-red-700'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50 text-gray-700'
                    }`}
                  >
                    {val === 'True' ? '✓ True' : '✗ False'}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Answer input */}
          <div className="rounded-xl border bg-white p-5 shadow-sm space-y-4">
            <h3 className="font-semibold text-gray-900 text-sm">Your Answer</h3>

            {/* Text answer (for non-MCQ, non-true-false) */}
            {(!question.options || question.options.length === 0)
              && question.question_type !== 'true-or-false' && (
              <textarea
                ref={textareaRef}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={4}
                placeholder={
                  question.question_type === 'fill-in-the-blank'
                    ? 'Fill in the blank...'
                    : 'Type your answer here... (⌘+Enter to submit)'
                }
                className="w-full resize-none rounded-lg border border-gray-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            )}

            {/* Show selected answer preview for MCQ/true-false */}
            {(question.options?.length || question.question_type === 'true-or-false') && answer && (
              <div className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-2 text-sm text-blue-800">
                Selected: <strong>{answer}</strong>
              </div>
            )}

            {/* Handwritten answer upload */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => fileRef.current?.click()}
                className="rounded-lg border border-dashed border-gray-300 px-4 py-2 text-sm text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-colors"
              >
                📸 Upload handwritten answer
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleImageUpload}
              />
              {imagePreview && (
                <div className="relative">
                  <img
                    src={imagePreview}
                    alt="Handwritten answer"
                    className="h-16 w-16 rounded-lg border object-cover"
                  />
                  <button
                    onClick={() => { setImageBase64(null); setImagePreview(null); }}
                    className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-red-500 text-white text-xs flex items-center justify-center"
                  >
                    ✕
                  </button>
                </div>
              )}
            </div>

            {/* Submit button */}
            <div className="flex justify-between items-center pt-2">
              <button
                onClick={handleComplete}
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                End session early
              </button>
              <button
                onClick={handleSubmitAnswer}
                disabled={!answer && !imageBase64}
                className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40 transition-colors"
              >
                Submit Answer →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Grading Phase */}
      {phase === 'grading' && (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-purple-200 border-t-purple-600" />
          <p className="text-sm text-gray-600 font-medium">AI is grading your answer...</p>
          <p className="text-xs text-gray-400">This may take a few seconds</p>
        </div>
      )}

      {/* Graded Phase — show feedback */}
      {phase === 'graded' && gradingResult && (
        <div className="space-y-6">
          {/* Result banner */}
          <div className={`rounded-xl border-2 p-6 ${
            gradingResult.is_correct
              ? 'border-green-200 bg-green-50'
              : 'border-red-200 bg-red-50'
          }`}>
            <div className="flex items-center gap-3 mb-3">
              <span className="text-3xl">
                {gradingResult.is_correct ? '✅' : '❌'}
              </span>
              <div>
                <h3 className={`text-lg font-bold ${gradingResult.is_correct ? 'text-green-800' : 'text-red-800'}`}>
                  {gradingResult.is_correct ? 'Correct!' : 'Not quite right'}
                </h3>
                <p className="text-sm text-gray-600">
                  Score: {Math.round(gradingResult.score * 100)}%
                </p>
              </div>
            </div>

            {/* OCR notice */}
            {gradingResult.was_handwritten && gradingResult.ocr_text && (
              <div className="mb-3 rounded-lg bg-white/70 border border-gray-200 p-3">
                <p className="text-xs font-medium text-gray-500 mb-1">📸 OCR recognized text:</p>
                <p className="text-sm text-gray-700 italic">&quot;{gradingResult.ocr_text}&quot;</p>
              </div>
            )}

            {/* Feedback */}
            <div className="mt-3">
              <h4 className="text-sm font-semibold text-gray-700 mb-1">Feedback</h4>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                {gradingResult.feedback}
              </p>
            </div>

            {/* Student answer vs correct answer */}
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg bg-white/80 p-3">
                <p className="text-xs font-medium text-gray-500 mb-1">Your answer</p>
                <p className="text-sm text-gray-800">{gradingResult.student_answer}</p>
              </div>
              {gradingResult.correct_answer && (
                <div className="rounded-lg bg-white/80 p-3">
                  <p className="text-xs font-medium text-gray-500 mb-1">Expected answer</p>
                  <p className="text-sm text-gray-800">{gradingResult.correct_answer}</p>
                </div>
              )}
            </div>
          </div>

          {/* Source references */}
          {gradingResult.source_references.length > 0 && (
            <div className="rounded-xl border bg-white p-5 shadow-sm">
              <button
                onClick={() => setShowSources(!showSources)}
                className="flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                📚 {showSources ? 'Hide' : 'View'} source references ({gradingResult.source_references.length})
              </button>
              {showSources && (
                <div className="mt-3 space-y-3">
                  {gradingResult.source_references.map((ref, i) => (
                    <SourceCard
                      key={i}
                      source={ref}
                      index={i}
                      onOpenDocument={(src) => {
                        if (src.document_id) {
                          setViewingSource({
                            documentId: src.document_id,
                            documentName: src.document_name || 'Document',
                            page: src.page_number ?? undefined,
                          });
                        }
                      }}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Navigation */}
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-500">
              {answeredCount}/{totalQuestions} answered · {correctCount} correct
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleComplete}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Finish Session
              </button>
              {answeredCount < totalQuestions && (
                <button
                  onClick={loadNextQuestion}
                  className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
                >
                  Next Question →
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Completed Phase — session summary */}
      {phase === 'completed' && sessionResult && (
        <div className="space-y-6">
          <div className="rounded-xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-white p-8 text-center">
            <div className="text-5xl mb-4">
              {sessionResult.accuracy >= 0.8 ? '🏆' : sessionResult.accuracy >= 0.6 ? '👍' : '💪'}
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-1">Practice Complete!</h2>
            {subjectInfo && (
              <p className="text-sm text-gray-500 mb-3">{subjectInfo.icon || '📚'} {subjectInfo.name}</p>
            )}
            <div className="flex items-center justify-center gap-6 mt-4">
              <div>
                <p className={`text-3xl font-bold ${
                  sessionResult.accuracy >= 0.8 ? 'text-green-600'
                  : sessionResult.accuracy >= 0.6 ? 'text-blue-600'
                  : 'text-orange-600'
                }`}>
                  {Math.round(sessionResult.accuracy * 100)}%
                </p>
                <p className="text-xs text-gray-500">Accuracy</p>
              </div>
              <div className="h-10 w-px bg-gray-200" />
              <div>
                <p className="text-3xl font-bold text-green-600">
                  {sessionResult.correct_count}/{sessionResult.total_questions}
                </p>
                <p className="text-xs text-gray-500">Correct</p>
              </div>
              <div className="h-10 w-px bg-gray-200" />
              <div>
                <p className="text-3xl font-bold text-gray-700">
                  {fmtTime(elapsed)}
                </p>
                <p className="text-xs text-gray-500">Time</p>
              </div>
            </div>
            {/* Encouragement message */}
            <p className="mt-4 text-sm text-gray-600">
              {sessionResult.accuracy >= 0.8
                ? 'Excellent work! You have a strong grasp of this material. 🌟'
                : sessionResult.accuracy >= 0.6
                  ? 'Good effort! Review the questions below to strengthen your understanding.'
                  : 'Keep practicing! Review the feedback below and try again to improve.'}
            </p>
          </div>

          {/* Answer review */}
          {(sessionResult.answers?.length ?? 0) > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                📋 Answer Review ({sessionResult.answers?.filter(a => a.is_correct).length}/{sessionResult.answers?.length} correct)
              </h3>
              <div className="space-y-4">
                {sessionResult.answers?.map((ans, i) => (
                  <div
                    key={i}
                    className={`rounded-xl border p-5 ${
                      ans.is_correct ? 'border-green-200 bg-green-50/50' : 'border-red-200 bg-red-50/50'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-xl mt-0.5">{ans.is_correct ? '✅' : '❌'}</span>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 text-sm mb-1">
                          <span className="text-gray-400 mr-1">Q{i + 1}.</span> {ans.question_text}
                        </p>
                        <div className="grid gap-2 sm:grid-cols-2 text-sm mt-2">
                          <div className="rounded-lg bg-white p-2">
                            <p className="text-xs text-gray-500">Your answer</p>
                            <p className="text-gray-800">{ans.student_answer}</p>
                          </div>
                          {ans.correct_answer && (
                            <div className="rounded-lg bg-white p-2">
                              <p className="text-xs text-gray-500">Expected</p>
                              <p className="text-gray-800">{ans.correct_answer}</p>
                            </div>
                          )}
                        </div>
                        <p className="text-sm text-gray-600 mt-2">{ans.feedback}</p>

                        {/* Source references */}
                        {ans.source_references.length > 0 && (
                          <details className="mt-2">
                            <summary className="text-xs text-blue-600 cursor-pointer hover:underline">
                              📚 {ans.source_references.length} source{ans.source_references.length > 1 ? 's' : ''}
                            </summary>
                            <div className="mt-2 space-y-2">
                              {ans.source_references.map((ref, j) => (
                                <SourceCard
                                  key={j}
                                  source={ref}
                                  index={j}
                                  onOpenDocument={(src) => {
                                    if (src.document_id) {
                                      setViewingSource({
                                        documentId: src.document_id,
                                        documentName: src.document_name || 'Document',
                                        page: src.page_number ?? undefined,
                                      });
                                    }
                                  }}
                                />
                              ))}
                            </div>
                          </details>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 justify-center flex-wrap">
            {subjectInfo && (
              <button
                onClick={() => router.push(`/student/subjects/${subjectInfo.id}?tab=practice`)}
                className="rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
              >
                🔄 Practice Again
              </button>
            )}
            <Link
              href={ROUTES.STUDENT_PROGRESS}
              className="rounded-lg border border-gray-300 px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              📊 View Progress
            </Link>
            <Link
              href={ROUTES.STUDENT_SUBJECTS}
              className="rounded-lg border border-gray-300 px-6 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              ← Back to Subjects
            </Link>
          </div>
        </div>
      )}

      {/* PDF Viewer Modal for source references */}
      {viewingSource && (
        <PDFViewerModal
          documentId={viewingSource.documentId}
          filename={viewingSource.documentName}
          initialPage={viewingSource.page}
          onClose={() => setViewingSource(null)}
        />
      )}
    </main>
  );
}

function SourceCard({
  source,
  index,
  onOpenDocument,
}: {
  source: SourceReference;
  index: number;
  onOpenDocument?: (source: SourceReference) => void;
}) {
  const isClickable = !!source.document_id;

  return (
    <div
      className={`rounded-lg border border-gray-200 bg-gray-50 p-3 ${
        isClickable
          ? 'cursor-pointer hover:border-blue-300 hover:bg-blue-50/50 transition-colors'
          : ''
      }`}
      onClick={() => isClickable && onOpenDocument?.(source)}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onKeyDown={(e) => {
        if (isClickable && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onOpenDocument?.(source);
        }
      }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-medium text-gray-500">
          Source #{index + 1}
          {source.page_number != null && ` · Page ${source.page_number}`}
          {source.document_name && ` · ${source.document_name}`}
        </span>
        <span className="text-xs text-gray-400">
          score: {source.score.toFixed(3)}
        </span>
        {isClickable && (
          <span className="ml-auto text-xs text-blue-500 font-medium">
            📄 Open in document →
          </span>
        )}
      </div>
      <p className="text-xs text-gray-700 line-clamp-3">{source.content}</p>
    </div>
  );
}
