'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth, useSubjects } from '@/lib/hooks';
import { documentAPI } from '@/lib/api';
import { DocumentRead } from '@/lib/types';
import { EDUCATION_LEVELS, ROUTES, DOCUMENT_CATEGORIES } from '@/config/constants';


const IN_PROGRESS: DocumentRead['ingestion_status'][] = ['pending', 'ingesting'];

export default function DocumentsPage() {
  const router = useRouter();
  const { user } = useAuth();

  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showArchived, setShowArchived] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null); // id of doc being archived/restored
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Filters for document list
  const [filterLevel, setFilterLevel] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  // Upload form: subject suggestions based on selected level
  const [selectedLevel, setSelectedLevel] = useState('');
  const [customSubject, setCustomSubject] = useState(false);
  const { subjects: levelSubjects } = useSubjects(selectedLevel || undefined);

  // Auth guard — must be a useEffect, never an early return before other hooks
  useEffect(() => {
    if (user && user.role !== 'admin') {
      router.push(ROUTES.DASHBOARD);
    }
  }, [user, router]);

  const loadDocuments = useCallback(async (includeArchived: boolean) => {
    setIsLoading(true);
    try {
      const docs = await documentAPI.list(undefined, undefined, 0, 100, includeArchived);
      setDocuments(docs);
    } catch {
      setError('Failed to load documents.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments(showArchived);
  }, [showArchived, loadDocuments]);

  // Poll every 3 s while any doc is pending or ingesting
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    const hasInProgress = documents.some((d) => IN_PROGRESS.includes(d.ingestion_status));
    if (hasInProgress && !pollingRef.current) {
      pollingRef.current = setInterval(async () => {
        const docs = await documentAPI.list(undefined, undefined, 0, 100, showArchived);
        setDocuments(docs);
        const stillRunning = docs.some((d) => IN_PROGRESS.includes(d.ingestion_status));
        if (!stillRunning && pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      }, 3000);
    } else if (!hasInProgress && pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    return () => {
      if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [documents]);

  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    const formData = new FormData(e.currentTarget);
    const file = formData.get('file') as File;
    const subject = formData.get('subject') as string;
    const level = formData.get('level') as string;
    const year = formData.get('year') as string;
    const duration = formData.get('duration') as string;
    const documentCategory = formData.get('document_category') as string;

    if (!file || !subject || !level || !year) {
      setError('Please fill in all required fields');
      return;
    }

    setUploading(true);
    try {
      await documentAPI.uploadAdmin(file, {
        subject,
        level,
        year,
        official_duration_minutes: duration ? parseInt(duration, 10) : undefined,
        document_category: documentCategory || undefined,
      });
      setSuccess('Document uploaded and queued for ingestion!');
      (e.target as HTMLFormElement).reset();
      if (fileInputRef.current) fileInputRef.current.value = '';
      setSelectedLevel('');
      setCustomSubject(false);
      loadDocuments(showArchived);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleArchive = async (doc: DocumentRead) => {
    setActionId(doc.id);
    setError('');
    try {
      await documentAPI.archive(doc.id);
      setSuccess(`"${doc.filename}" archived.`);
      loadDocuments(showArchived);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Archive failed');
    } finally {
      setActionId(null);
    }
  };

  const handleRestore = async (doc: DocumentRead) => {
    setActionId(doc.id);
    setError('');
    try {
      await documentAPI.restore(doc.id);
      setSuccess(`"${doc.filename}" restored.`);
      loadDocuments(showArchived);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Restore failed');
    } finally {
      setActionId(null);
    }
  };

  const active = documents.filter((d) => !d.is_archived);
  const archived = documents.filter((d) => d.is_archived);
  const baseList = showArchived ? archived : active;
  const displayed = baseList.filter((d) => {
    if (filterLevel && d.level !== filterLevel) return false;
    if (filterStatus && d.ingestion_status !== filterStatus) return false;
    return true;
  });

  return (
    <>
      <main className="container py-8">
        <div className="grid gap-8 lg:grid-cols-3">
          {/* ── Upload Form ── */}
          <div className="lg:col-span-1">
            <div className="card sticky top-4">
              <h2 className="mb-4 font-semibold text-gray-900">Upload Document</h2>

              <form onSubmit={handleUpload} className="space-y-4">
                <div>
                  <label htmlFor="file" className="block text-sm font-medium text-gray-700">PDF File</label>
                  <input ref={fileInputRef} type="file" id="file" name="file" accept=".pdf"
                    required disabled={uploading} className="mt-1 w-full" />
                </div>

                <div>
                  <label htmlFor="level" className="block text-sm font-medium text-gray-700">Level</label>
                  <select
                    id="level"
                    name="level"
                    required
                    disabled={uploading}
                    className="mt-1 w-full"
                    value={selectedLevel}
                    onChange={(e) => { setSelectedLevel(e.target.value); setCustomSubject(false); }}
                  >
                    <option value="">Select level</option>
                    {EDUCATION_LEVELS.map((l) => (
                      <option key={l.value} value={l.value}>{l.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="subject" className="block text-sm font-medium text-gray-700">Subject</label>
                  {selectedLevel && levelSubjects.length > 0 && !customSubject ? (
                    <select
                      id="subject-select"
                      name="subject"
                      required
                      disabled={uploading}
                      className="mt-1 w-full"
                      onChange={(e) => {
                        if (e.target.value === '_custom') {
                          setCustomSubject(true);
                        }
                      }}
                    >
                      <option value="">Select subject</option>
                      {levelSubjects.map((s) => (
                        <option key={s.id} value={s.name}>
                          {s.icon || '📖'} {s.name}
                        </option>
                      ))}
                      <option value="_custom">✏️ Custom (type below)</option>
                    </select>
                  ) : (
                    <>
                      <input type="text" id="subject" name="subject" placeholder="e.g., Mathematics"
                        required disabled={uploading} className="mt-1 w-full" />
                      {customSubject && (
                        <button
                          type="button"
                          onClick={() => setCustomSubject(false)}
                          className="mt-1 text-xs text-blue-600 hover:underline"
                        >
                          ← Back to subject list
                        </button>
                      )}
                    </>
                  )}
                  {selectedLevel && levelSubjects.length === 0 && (
                    <p className="mt-1 text-xs text-amber-600">
                      No subjects found for {selectedLevel}. Type manually or seed defaults.
                    </p>
                  )}
                </div>

                <div>
                  <label htmlFor="document_category" className="block text-sm font-medium text-gray-700">Category</label>
                  <select id="document_category" name="document_category" disabled={uploading} className="mt-1 w-full">
                    {DOCUMENT_CATEGORIES.map((c) => (
                      <option key={c.value} value={c.value}>{c.icon} {c.label}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="year" className="block text-sm font-medium text-gray-700">Year</label>
                  <input type="text" id="year" name="year" placeholder="e.g., 2023"
                    required disabled={uploading} className="mt-1 w-full" />
                </div>

                <div>
                  <label htmlFor="duration" className="block text-sm font-medium text-gray-700">
                    Official Duration (minutes, optional)
                  </label>
                  <input type="number" id="duration" name="duration" placeholder="e.g., 120"
                    disabled={uploading} className="mt-1 w-full" />
                </div>

                {error && <div className="rounded bg-red-50 p-3 text-sm text-red-700">{error}</div>}
                {success && <div className="rounded bg-green-50 p-3 text-sm text-green-700">{success}</div>}

                <button type="submit" disabled={uploading || isLoading}
                  className="w-full bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:opacity-50">
                  {uploading ? 'Uploading…' : 'Upload'}
                </button>
              </form>
            </div>
          </div>

          {/* ── Documents List ── */}
          <div className="lg:col-span-2">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">
                {showArchived ? 'Archived Documents' : 'Active Documents'}
                <span className="ml-2 text-sm font-normal text-gray-500">
                  ({displayed.length}{displayed.length !== baseList.length ? ` of ${baseList.length}` : ''})
                </span>
              </h2>
              <button
                onClick={() => { setError(''); setSuccess(''); setShowArchived((v) => !v); }}
                className={`rounded px-3 py-1.5 text-xs font-medium transition ${
                  showArchived
                    ? 'bg-amber-100 text-amber-800 hover:bg-amber-200'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {showArchived ? '← Back to Active' : `🗄 Show Archived (${archived.length})`}
              </button>
            </div>

            {/* ── Filters ── */}
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <select
                value={filterLevel}
                onChange={(e) => setFilterLevel(e.target.value)}
                className="rounded border border-gray-300 px-2 py-1.5 text-sm"
              >
                <option value="">All Levels</option>
                {EDUCATION_LEVELS.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="rounded border border-gray-300 px-2 py-1.5 text-sm"
              >
                <option value="">All Statuses</option>
                <option value="completed">✓ Ready</option>
                <option value="pending">⏳ Pending</option>
                <option value="ingesting">⚙ Ingesting</option>
                <option value="failed">✗ Failed</option>
              </select>
              {(filterLevel || filterStatus) && (
                <button
                  onClick={() => { setFilterLevel(''); setFilterStatus(''); }}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Clear filters
                </button>
              )}
            </div>

            {isLoading ? (
              <div className="flex-center"><p className="text-gray-600">Loading…</p></div>
            ) : displayed.length > 0 ? (
              <div className="space-y-3">
                {displayed.map((doc) => {
                  const catInfo = DOCUMENT_CATEGORIES.find((c) => c.value === doc.document_category);
                  return (
                  <div key={doc.id} className={`card ${
                    doc.is_archived ? 'border-amber-200 bg-amber-50' : ''
                  }`}>
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                          <Link
                            href={ROUTES.ADMIN_DOCUMENT_DETAIL(doc.id)}
                            className="font-semibold text-blue-700 hover:text-blue-900 hover:underline truncate"
                          >
                            {catInfo?.icon || '📄'} {doc.filename}
                          </Link>
                          {doc.is_personal && (
                            <span className="shrink-0 rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-medium text-purple-700">
                              👤 Student
                            </span>
                          )}
                          {(doc.comment_count ?? 0) > 0 && (
                            <span className="shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-medium text-blue-700">
                              💬 {doc.comment_count}
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">
                          {doc.subject} · {doc.level} · {doc.year}
                        </p>
                        {doc.uploader_name && (
                          <p className="text-xs text-gray-500">
                            Uploaded by {doc.uploader_name}
                          </p>
                        )}
                        {doc.official_duration_minutes && (
                          <p className="text-xs text-gray-500">Duration: {doc.official_duration_minutes} min</p>
                        )}
                        {doc.is_archived && (
                          <div className="mt-1">
                            {doc.archive_reason && (
                              <p className="text-xs text-amber-800 italic">
                                Reason: {doc.archive_reason}
                              </p>
                            )}
                            <p className="text-xs text-amber-700">
                              Archived {doc.archived_at ? new Date(doc.archived_at).toLocaleDateString() : ''}
                              {doc.archiver_name && ` by ${doc.archiver_name}`}
                            </p>
                          </div>
                        )}
                      </div>

                      <div className="flex shrink-0 flex-col items-end gap-2">
                        {/* Ingestion status badge */}
                        {IN_PROGRESS.includes(doc.ingestion_status) ? (
                          <div className="w-32">
                            <div className="mb-1 flex items-center justify-between">
                              <span className="text-xs font-medium text-yellow-700">
                                {doc.ingestion_status === 'ingesting' ? '⚙ Processing…' : '⏳ Queued'}
                              </span>
                            </div>
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-yellow-100">
                              <div
                                className={`h-full rounded-full bg-yellow-400 ${
                                  doc.ingestion_status === 'ingesting'
                                    ? 'animate-[progress_2s_ease-in-out_infinite]'
                                    : 'w-1/4'
                                }`}
                                style={doc.ingestion_status === 'ingesting'
                                  ? { animation: 'indeterminate 1.5s ease-in-out infinite' }
                                  : { width: '25%' }}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                            doc.ingestion_status === 'completed' ? 'bg-green-100 text-green-800'
                            : doc.ingestion_status === 'failed'   ? 'bg-red-100 text-red-800'
                            : 'bg-gray-100 text-gray-800'
                          }`}>
                            {doc.ingestion_status === 'completed' ? '✓ Ready' : '✗ Failed'}
                          </span>
                        )}

                        {/* Archive / Restore button */}
                        {doc.is_archived ? (
                          <button
                            onClick={() => handleRestore(doc)}
                            disabled={actionId === doc.id}
                            className="rounded bg-green-100 px-2 py-1 text-xs font-medium text-green-800 hover:bg-green-200 disabled:opacity-50"
                          >
                            {actionId === doc.id ? '…' : '↩ Restore'}
                          </button>
                        ) : (
                          <button
                            onClick={() => handleArchive(doc)}
                            disabled={actionId === doc.id}
                            className="rounded bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800 hover:bg-amber-200 disabled:opacity-50"
                          >
                            {actionId === doc.id ? '…' : '🗄 Archive'}
                          </button>
                        )}

                        {/* View detail link */}
                        <Link
                          href={ROUTES.ADMIN_DOCUMENT_DETAIL(doc.id)}
                          className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-200"
                        >
                          👁 View
                        </Link>
                      </div>
                    </div>
                  </div>
                  );
                })}
              </div>
            ) : (
              <div className="card text-center">
                <p className="text-gray-600">
                  {showArchived ? 'No archived documents.' : 'No documents uploaded yet.'}
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  );
}
