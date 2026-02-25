'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks';
import { subjectAPI, documentAPI, practiceAPI } from '@/lib/api';
import {
  SubjectDetailRead,
  DocumentRead,
  PracticeSessionRead,
} from '@/lib/types';
import { ROUTES, EDUCATION_LEVELS, DOCUMENT_CATEGORIES } from '@/config/constants';
import PDFViewerModal from '@/components/PDFViewerModal';

type Tab = 'documents' | 'practice' | 'chat';

const CATEGORY_ICONS: Record<string, string> = Object.fromEntries(
  DOCUMENT_CATEGORIES.map(({ value, icon }) => [value, icon]),
);

export default function SubjectWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const subjectId = params.id as string;

  const [subject, setSubject] = useState<SubjectDetailRead | null>(null);
  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [practiceSessions, setPracticeSessions] = useState<PracticeSessionRead[]>([]);

  // Read initial tab from ?tab= query param, default to 'documents'
  const tabParam = searchParams.get('tab');
  const initialTab: Tab =
    tabParam === 'practice' || tabParam === 'chat' || tabParam === 'documents'
      ? tabParam
      : 'documents';
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Upload state
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadMeta, setUploadMeta] = useState({
    year: String(new Date().getFullYear()),
    document_category: 'exam_paper' as string,
    official_duration_minutes: '',
  });

  // Practice start state
  const [startingPractice, setStartingPractice] = useState(false);
  const [practiceMode, setPracticeMode] = useState<'practice' | 'real_exam' | null>(null);
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null);

  // PDF viewer state
  const [viewingDoc, setViewingDoc] = useState<DocumentRead | null>(null);

  const closePdfViewer = () => {
    setViewingDoc(null);
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [subjectData, docs] = await Promise.all([
        subjectAPI.get(subjectId),
        subjectAPI.getDocuments(subjectId),
      ]);
      setSubject(subjectData);
      setDocuments(docs);

      // Load practice sessions for this subject
      try {
        const sessions = await practiceAPI.list(0, 50, subjectId);
        setPracticeSessions(sessions);
      } catch {
        /* practice might not have sessions yet */
      }
    } catch {
      setError('Failed to load subject data');
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => {
    if (user) loadData();
  }, [user, loadData]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !subject) return;

    setUploading(true);
    try {
      await documentAPI.uploadStudent(file, {
        subject: subject.name,
        level: subject.level,
        year: uploadMeta.year,
        document_category: uploadMeta.document_category,
        subject_id: subject.id,
        official_duration_minutes: uploadMeta.official_duration_minutes
          ? Number(uploadMeta.official_duration_minutes)
          : undefined,
      });
      setShowUpload(false);
      if (fileRef.current) fileRef.current.value = '';
      await loadData();
    } catch {
      setError('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const handleStartPractice = async (mode: 'practice' | 'real_exam' = 'practice', docId?: string) => {
    if (!subject) return;
    setStartingPractice(true);
    try {
      const session = await practiceAPI.start({
        subject_id: subject.id,
        document_id: docId,
        question_count: mode === 'real_exam' ? 15 : 5,
        mode,
      });
      router.push(ROUTES.STUDENT_PRACTICE_SESSION(session.id));
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to start practice session');
    } finally {
      setStartingPractice(false);
    }
  };

  const handleAskAI = () => {
    if (!subject) return;
    const collection = `${subject.level}_${subject.name}`.replace(/ /g, '_');
    router.push(`${ROUTES.STUDENT_ASK_AI}?collection=${encodeURIComponent(collection)}&subject=${encodeURIComponent(subject.name)}`);
  };

  if (!user) return null;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
      </div>
    );
  }

  if (!subject) {
    return (
      <main className="container py-8">
        <div className="rounded-lg border bg-white p-12 text-center">
          <p className="text-gray-600">Subject not found.</p>
          <Link href={ROUTES.STUDENT_SUBJECTS} className="text-blue-600 hover:underline mt-2 inline-block">
            ← Back to Subjects
          </Link>
        </div>
      </main>
    );
  }

  const levelLabel = EDUCATION_LEVELS.find((l) => l.value === subject.level)?.label ?? subject.level;
  const examPapers = documents.filter((d) => !d.document_category || d.document_category === 'exam_paper');
  const otherDocs = documents.filter((d) => d.document_category && d.document_category !== 'exam_paper');

  return (
    <main className="container py-8">
      {/* Breadcrumb */}
      <div className="mb-4 flex items-center gap-2 text-sm text-gray-500">
        <Link href={ROUTES.STUDENT_SUBJECTS} className="hover:text-blue-600 transition-colors">
          Subjects
        </Link>
        <span>/</span>
        <span className="text-gray-900 font-medium">{subject.icon} {subject.name}</span>
      </div>

      {/* Header */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span className="text-4xl">{subject.icon || '📖'}</span>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{subject.name}</h1>
            <p className="text-sm text-gray-500">
              {levelLabel} · {documents.length} document{documents.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={handleAskAI}
            className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 transition-colors"
          >
            🤖 Ask AI
          </button>
          <button
            onClick={() => handleStartPractice('practice')}
            disabled={startingPractice || examPapers.filter(d => d.ingestion_status === 'completed').length === 0}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {startingPractice ? 'Starting...' : '✏️ Practice Now'}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 p-4 text-red-700 text-sm">{error}</div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b mb-6">
        {(['documents', 'practice', 'chat'] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab === 'documents' && `📄 Documents (${documents.length})`}
            {tab === 'practice' && `✏️ Practice`}
            {tab === 'chat' && '🤖 Ask AI'}
          </button>
        ))}
      </div>

      {/* PDF Viewer Modal */}
      {viewingDoc && (
        <PDFViewerModal
          documentId={viewingDoc.id}
          filename={viewingDoc.filename}
          subtitle={`${viewingDoc.subject} · ${viewingDoc.year}${viewingDoc.page_count ? ` · ${viewingDoc.page_count} pages` : ''}`}
          totalPages={viewingDoc.page_count}
          onClose={closePdfViewer}
        />
      )}

      {/* Tab Content */}
      {activeTab === 'documents' && (
        <div className="space-y-6">
          {/* Upload button */}
          <div className="flex justify-end">
            <button
              onClick={() => setShowUpload(!showUpload)}
              className="rounded-lg border border-blue-600 bg-white px-4 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50 transition-colors"
            >
              {showUpload ? '✕ Cancel' : '＋ Upload Document'}
            </button>
          </div>

          {/* Upload form */}
          {showUpload && (
            <form onSubmit={handleUpload} className="rounded-lg border bg-white p-5 shadow-sm space-y-4">
              <h3 className="font-semibold text-gray-900">Upload to {subject.name}</h3>
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium text-gray-700">PDF File *</label>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf"
                  required
                  className="block w-full text-sm text-gray-500 file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-gray-700">Category *</label>
                  <select
                    value={uploadMeta.document_category}
                    onChange={(e) => setUploadMeta((p) => ({ ...p, document_category: e.target.value }))}
                    className="input"
                    required
                  >
                    {DOCUMENT_CATEGORIES.map(({ value, label, icon }) => (
                      <option key={value} value={value}>{icon} {label}</option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-gray-700">Year *</label>
                  <input
                    type="text"
                    value={uploadMeta.year}
                    onChange={(e) => setUploadMeta((p) => ({ ...p, year: e.target.value }))}
                    className="input"
                    required
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-gray-700">Duration (min)</label>
                  <input
                    type="number"
                    value={uploadMeta.official_duration_minutes}
                    onChange={(e) => setUploadMeta((p) => ({ ...p, official_duration_minutes: e.target.value }))}
                    className="input"
                    min={1}
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={uploading}
                className="btn-primary px-5 py-2 disabled:opacity-60"
              >
                {uploading ? 'Uploading...' : 'Upload'}
              </button>
            </form>
          )}

          {/* Exam Papers section */}
          {examPapers.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">📝 Exam Papers</h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {examPapers.map((doc) => (
                  <DocumentCard
                    key={doc.id}
                    doc={doc}
                    onView={() => setViewingDoc(doc)}
                    onPractice={() => handleStartPractice('real_exam', doc.id)}
                    startingPractice={startingPractice}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Other Documents */}
          {otherDocs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">📂 Study Materials</h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {otherDocs.map((doc) => (
                  <DocumentCard
                    key={doc.id}
                    doc={doc}
                    onView={() => setViewingDoc(doc)}
                  />
                ))}
              </div>
            </div>
          )}

          {documents.length === 0 && (
            <div className="rounded-lg border bg-white p-12 text-center">
              <div className="text-4xl mb-3">📄</div>
              <p className="text-gray-600 font-medium">No documents yet</p>
              <p className="text-sm text-gray-400 mt-1">
                Upload exam papers, marking schemes, or notes to start practicing.
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'practice' && (
        <div className="space-y-6">
          {/* Practice mode cards */}
          <div className="grid gap-4 sm:grid-cols-2">
            {/* Subject-wide practice */}
            <div className="rounded-xl border-2 border-blue-200 bg-blue-50/30 p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">📚</span>
                <h3 className="font-semibold text-gray-900">Subject Practice</h3>
              </div>
              <p className="text-sm text-gray-600 mb-4">
                Questions from <strong>all exam papers</strong> in this subject, mixed together.
                Great for broad revision and discovering weak topics.
              </p>
              <button
                onClick={() => handleStartPractice('practice')}
                disabled={startingPractice || examPapers.filter(d => d.ingestion_status === 'completed').length === 0}
                className="w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {startingPractice ? 'Starting...' : '✏️ Start Subject Practice'}
              </button>
            </div>

            {/* Real exam simulation */}
            <div className="rounded-xl border-2 border-amber-200 bg-amber-50/30 p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">🎯</span>
                <h3 className="font-semibold text-gray-900">Real Exam Simulation</h3>
              </div>
              <p className="text-sm text-gray-600 mb-3">
                Practice with a <strong>single exam paper</strong> as if it were the real exam.
                Pick a paper or let the system choose randomly.
              </p>

              {/* Paper selector */}
              {practiceMode === 'real_exam' ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-gray-700">Select exam paper:</label>
                    <button
                      onClick={() => { setPracticeMode(null); setSelectedPaperId(null); }}
                      className="text-xs text-gray-400 hover:text-gray-600"
                    >
                      Cancel
                    </button>
                  </div>
                  <select
                    value={selectedPaperId || ''}
                    onChange={(e) => setSelectedPaperId(e.target.value || null)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-amber-500 focus:ring-1 focus:ring-amber-500"
                  >
                    <option value="">🎲 Random paper</option>
                    {examPapers
                      .filter(d => d.ingestion_status === 'completed')
                      .map(d => (
                        <option key={d.id} value={d.id}>
                          {d.filename} ({d.year})
                          {d.official_duration_minutes ? ` — ${d.official_duration_minutes}min` : ''}
                        </option>
                      ))}
                  </select>
                  <button
                    onClick={() => handleStartPractice('real_exam', selectedPaperId || undefined)}
                    disabled={startingPractice}
                    className="w-full rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-amber-700 transition-colors disabled:opacity-50"
                  >
                    {startingPractice ? 'Starting...' : '🎯 Start Exam'}
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setPracticeMode('real_exam')}
                  disabled={examPapers.filter(d => d.ingestion_status === 'completed').length === 0}
                  className="w-full rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-amber-700 transition-colors disabled:opacity-50"
                >
                  🎯 Start Real Exam
                </button>
              )}
            </div>
          </div>

          {examPapers.filter(d => d.ingestion_status === 'completed').length === 0 && (
            <p className="text-center text-xs text-gray-400">
              Upload and ingest at least one exam paper to start practicing.
            </p>
          )}

          {/* Practice history */}
          {practiceSessions.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Past Practice Sessions</h3>
              <div className="space-y-2">
                {practiceSessions.map((session) => (
                  <Link
                    key={session.id}
                    href={ROUTES.STUDENT_PRACTICE_SESSION(session.id)}
                    className="flex items-center justify-between rounded-lg border bg-white px-4 py-3 hover:bg-gray-50 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {session.status === 'in_progress' ? '🔵' : session.status === 'completed' ? '✅' : '⏸️'}
                        {' '}{session.document_id ? '🎯 Exam Simulation' : '📚 Subject Practice'}
                      </p>
                      <p className="text-xs text-gray-500">
                        {session.answered_count}/{session.total_questions} answered
                        {session.status === 'completed' && ` · ${Math.round(session.accuracy * 100)}% accuracy`}
                        {' · '}{new Date(session.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <span className="text-gray-400">→</span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'chat' && (
        <div className="rounded-xl border bg-white p-8 text-center">
          <div className="text-5xl mb-4">🤖</div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Ask AI about {subject.name}</h3>
          <p className="text-sm text-gray-600 mb-6 max-w-md mx-auto">
            Chat with AI about this subject. Ask about concepts, exam questions, or get explanations from past papers.
          </p>
          <button
            onClick={handleAskAI}
            className="rounded-lg bg-purple-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-purple-700 transition-colors"
          >
            Open AI Chat →
          </button>
        </div>
      )}
    </main>
  );
}

function DocumentCard({
  doc,
  onView,
  onPractice,
  startingPractice,
}: {
  doc: DocumentRead;
  onView: () => void;
  onPractice?: () => void;
  startingPractice?: boolean;
}) {
  const categoryIcon = doc.document_category ? CATEGORY_ICONS[doc.document_category] || '📄' : '📄';
  const isReady = doc.ingestion_status === 'completed';

  const statusBadge: Record<string, { label: string; className: string }> = {
    pending: { label: '⏳ Pending', className: 'bg-yellow-100 text-yellow-700' },
    ingesting: { label: '⚙️ Processing', className: 'bg-blue-100 text-blue-700' },
    completed: { label: '✅ Ready', className: 'bg-green-100 text-green-700' },
    failed: { label: '❌ Failed', className: 'bg-red-100 text-red-700' },
  };
  const badge = statusBadge[doc.ingestion_status] ?? { label: doc.ingestion_status, className: 'bg-gray-100 text-gray-600' };

  return (
    <div className="card flex flex-col gap-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">{categoryIcon}</span>
          <div className="min-w-0">
            <h4 className="font-medium text-gray-900 text-sm truncate" title={doc.filename}>
              {doc.filename}
            </h4>
            <p className="text-xs text-gray-500">
              {doc.year}
              {doc.page_count ? ` · ${doc.page_count} pages` : ''}
              {doc.official_duration_minutes ? ` · ${doc.official_duration_minutes}min` : ''}
            </p>
          </div>
        </div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${badge.className}`}>
          {badge.label}
        </span>
      </div>

      <div className="mt-auto flex gap-2">
        <button
          onClick={onView}
          className="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          👁 View PDF
        </button>
        {onPractice && (
          <button
            onClick={onPractice}
            disabled={!isReady || startingPractice}
            className="flex-1 rounded-md bg-blue-600 px-2 py-1.5 text-xs font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            🎯 Exam Sim
          </button>
        )}
      </div>
    </div>
  );
}
