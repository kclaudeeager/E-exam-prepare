'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks';
import { documentAPI } from '@/lib/api';
import { DocumentRead, DocumentCommentRead, CommentType } from '@/lib/types';
import { ROUTES, ACCESS_TOKEN_KEY, API_ENDPOINTS, DOCUMENT_CATEGORIES } from '@/config/constants';

type Tab = 'preview' | 'comments' | 'details';

export default function AdminDocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const docId = params.id as string;

  const [doc, setDoc] = useState<DocumentRead | null>(null);
  const [comments, setComments] = useState<DocumentCommentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('preview');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // PDF viewer state
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(true);
  const [pdfError, setPdfError] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageInput, setPageInput] = useState('1');

  // Comment form state
  const [newComment, setNewComment] = useState('');
  const [commentType, setCommentType] = useState<CommentType>('comment');
  const [commentPage, setCommentPage] = useState<string>('');
  const [highlightText, setHighlightText] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);

  // Archive modal state
  const [showArchiveModal, setShowArchiveModal] = useState(false);
  const [archiveReason, setArchiveReason] = useState('');
  const [archiving, setArchiving] = useState(false);

  // Editing comment
  const [editingCommentId, setEditingCommentId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState('');

  // Auth guard
  useEffect(() => {
    if (user && user.role !== 'admin') {
      router.push(ROUTES.DASHBOARD);
    }
  }, [user, router]);

  const loadDocument = useCallback(async () => {
    try {
      const data = await documentAPI.get(docId);
      setDoc(data);
    } catch {
      setError('Failed to load document');
    }
  }, [docId]);

  const loadComments = useCallback(async () => {
    try {
      const data = await documentAPI.listComments(docId);
      setComments(data);
    } catch { /* ignore */ }
  }, [docId]);

  // Load PDF blob
  useEffect(() => {
    let revoke: string | null = null;
    let cancelled = false;

    async function loadPdf() {
      setPdfLoading(true);
      setPdfError('');
      try {
        const token = typeof window !== 'undefined' ? localStorage.getItem(ACCESS_TOKEN_KEY) : null;
        if (!token) throw new Error('Not authenticated');
        const res = await fetch(API_ENDPOINTS.DOCUMENT_PDF(docId), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error('Failed to load PDF');
        const blob = await res.blob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        revoke = url;
        setPdfBlobUrl(url);
      } catch (err: unknown) {
        if (!cancelled) setPdfError(err instanceof Error ? err.message : 'Failed to load PDF');
      } finally {
        if (!cancelled) setPdfLoading(false);
      }
    }

    loadPdf();
    return () => { cancelled = true; if (revoke) URL.revokeObjectURL(revoke); };
  }, [docId]);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadDocument(), loadComments()]).finally(() => setLoading(false));
  }, [loadDocument, loadComments]);

  const goToPage = useCallback(
    (page: number) => {
      const p = Math.max(1, doc?.page_count ? Math.min(page, doc.page_count) : page);
      setCurrentPage(p);
      setPageInput(String(p));
    },
    [doc?.page_count],
  );

  const handlePageInputSubmit = () => {
    const p = parseInt(pageInput, 10);
    if (!isNaN(p) && p >= 1) goToPage(p);
  };

  // ── Comment actions ───────────────────────────────────────────────

  const handleAddComment = async () => {
    if (!newComment.trim()) return;
    setSubmittingComment(true);
    setError('');
    try {
      await documentAPI.addComment(docId, {
        content: newComment.trim(),
        comment_type: commentType,
        page_number: commentPage ? parseInt(commentPage, 10) : undefined,
        highlight_text: highlightText || undefined,
      });
      setNewComment('');
      setCommentPage('');
      setHighlightText('');
      setCommentType('comment');
      setSuccess('Comment added');
      setTimeout(() => setSuccess(''), 3000);
      loadComments();
      loadDocument(); // refresh comment count
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to add comment');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleUpdateComment = async (commentId: string) => {
    if (!editingContent.trim()) return;
    try {
      await documentAPI.updateComment(docId, commentId, { content: editingContent.trim() });
      setEditingCommentId(null);
      setEditingContent('');
      loadComments();
    } catch {
      setError('Failed to update comment');
    }
  };

  const handleToggleResolved = async (comment: DocumentCommentRead) => {
    try {
      await documentAPI.updateComment(docId, comment.id, { resolved: !comment.resolved });
      loadComments();
    } catch {
      setError('Failed to update comment');
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    if (!confirm('Delete this comment?')) return;
    try {
      await documentAPI.deleteComment(docId, commentId);
      loadComments();
      loadDocument();
    } catch {
      setError('Failed to delete comment');
    }
  };

  // ── Archive / Restore ─────────────────────────────────────────────

  const handleArchive = async () => {
    setArchiving(true);
    setError('');
    try {
      await documentAPI.archive(docId, archiveReason || undefined);
      setShowArchiveModal(false);
      setArchiveReason('');
      setSuccess('Document archived');
      setTimeout(() => setSuccess(''), 3000);
      loadDocument();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Archive failed');
    } finally {
      setArchiving(false);
    }
  };

  const handleRestore = async () => {
    setError('');
    try {
      await documentAPI.restore(docId);
      setSuccess('Document restored');
      setTimeout(() => setSuccess(''), 3000);
      loadDocument();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Restore failed');
    }
  };

  // ── Helpers ───────────────────────────────────────────────────────

  const categoryInfo = DOCUMENT_CATEGORIES.find((c) => c.value === doc?.document_category);
  const iframeSrc = pdfBlobUrl ? `${pdfBlobUrl}#page=${currentPage}` : '';

  const commentTypeConfig: Record<CommentType, { icon: string; label: string; color: string }> = {
    comment: { icon: '💬', label: 'Comment', color: 'bg-blue-100 text-blue-800' },
    highlight: { icon: '🖍️', label: 'Highlight', color: 'bg-yellow-100 text-yellow-800' },
    issue: { icon: '⚠️', label: 'Issue', color: 'bg-red-100 text-red-800' },
  };

  if (!user || user.role !== 'admin') return null;

  return (
    <main className="container py-6">
      {/* Breadcrumb + header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Link href={ROUTES.ADMIN_DOCUMENTS} className="text-sm text-gray-500 hover:text-blue-600">
            ← Back to Documents
          </Link>
          {doc && (
            <h1 className="mt-1 text-xl font-bold text-gray-900 truncate max-w-2xl">
              {categoryInfo?.icon || '📄'} {doc.filename}
            </h1>
          )}
        </div>
        {doc && (
          <div className="flex items-center gap-2">
            {doc.is_archived ? (
              <button
                onClick={handleRestore}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 transition-colors"
              >
                ↩ Restore Document
              </button>
            ) : (
              <button
                onClick={() => setShowArchiveModal(true)}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 transition-colors"
              >
                🗄 Archive
              </button>
            )}
          </div>
        )}
      </div>

      {/* Status banners */}
      {error && <div className="mb-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">{error}</div>}
      {success && <div className="mb-4 rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-700">{success}</div>}

      {/* Archive info banner */}
      {doc?.is_archived && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
          <div className="flex items-start gap-3">
            <span className="text-xl">🗄</span>
            <div>
              <p className="font-medium text-amber-900">This document is archived</p>
              {doc.archive_reason && (
                <p className="mt-1 text-sm text-amber-800">
                  <strong>Reason:</strong> {doc.archive_reason}
                </p>
              )}
              <p className="mt-1 text-xs text-amber-700">
                Archived {doc.archived_at ? new Date(doc.archived_at).toLocaleString() : ''}
                {doc.archiver_name && ` by ${doc.archiver_name}`}
              </p>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600" />
        </div>
      ) : doc ? (
        <>
          {/* Tab bar */}
          <div className="mb-4 flex gap-1 rounded-lg bg-gray-100 p-1">
            {(['preview', 'comments', 'details'] as Tab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {tab === 'preview' && '📄 Preview'}
                {tab === 'comments' && `💬 Comments (${comments.length})`}
                {tab === 'details' && '📋 Details'}
              </button>
            ))}
          </div>

          {/* ── Preview Tab ───────────────────────────────────────── */}
          {activeTab === 'preview' && (
            <div className="flex gap-4" style={{ height: 'calc(100vh - 260px)' }}>
              {/* PDF viewer */}
              <div className="flex-1 flex flex-col rounded-xl border bg-white overflow-hidden">
                {/* Page navigation */}
                <div className="flex items-center justify-between border-b px-4 py-2 bg-gray-50">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => goToPage(currentPage - 1)}
                      disabled={currentPage <= 1}
                      className="rounded bg-gray-200 px-2 py-1 text-xs font-medium hover:bg-gray-300 disabled:opacity-40"
                    >
                      ← Prev
                    </button>
                    <span className="text-xs text-gray-600">
                      Page{' '}
                      <input
                        type="text"
                        value={pageInput}
                        onChange={(e) => setPageInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handlePageInputSubmit()}
                        onBlur={handlePageInputSubmit}
                        className="w-10 rounded border px-1 py-0.5 text-center text-xs"
                      />
                      {doc.page_count ? ` of ${doc.page_count}` : ''}
                    </span>
                    <button
                      onClick={() => goToPage(currentPage + 1)}
                      disabled={doc.page_count ? currentPage >= doc.page_count : false}
                      className="rounded bg-gray-200 px-2 py-1 text-xs font-medium hover:bg-gray-300 disabled:opacity-40"
                    >
                      Next →
                    </button>
                  </div>
                  <span className="text-xs text-gray-400">{doc.filename}</span>
                </div>

                {/* PDF iframe */}
                <div className="flex-1">
                  {pdfLoading && (
                    <div className="flex h-full items-center justify-center text-sm text-gray-500 gap-2">
                      <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600" />
                      Loading PDF...
                    </div>
                  )}
                  {!pdfLoading && pdfError && (
                    <div className="flex h-full items-center justify-center text-sm text-red-600">{pdfError}</div>
                  )}
                  {!pdfLoading && !pdfError && pdfBlobUrl && (
                    <iframe
                      key={iframeSrc}
                      src={iframeSrc}
                      className="w-full h-full border-0"
                      title={doc.filename}
                    />
                  )}
                </div>
              </div>

              {/* Quick comment sidebar */}
              <div className="w-80 shrink-0 flex flex-col rounded-xl border bg-white overflow-hidden">
                <div className="border-b px-4 py-3 bg-gray-50">
                  <h3 className="text-sm font-semibold text-gray-900">
                    Quick Notes
                    <span className="ml-1 text-xs font-normal text-gray-500">({comments.length})</span>
                  </h3>
                </div>

                {/* Quick add form */}
                <div className="border-b p-3 space-y-2">
                  <textarea
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    placeholder="Add a note about this document..."
                    rows={2}
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <div className="flex items-center gap-2">
                    <select
                      value={commentType}
                      onChange={(e) => setCommentType(e.target.value as CommentType)}
                      className="rounded border px-2 py-1 text-xs"
                    >
                      <option value="comment">💬 Comment</option>
                      <option value="highlight">🖍️ Highlight</option>
                      <option value="issue">⚠️ Issue</option>
                    </select>
                    <input
                      type="number"
                      value={commentPage}
                      onChange={(e) => setCommentPage(e.target.value)}
                      placeholder="Pg #"
                      min={1}
                      className="w-14 rounded border px-2 py-1 text-xs"
                    />
                    <button
                      onClick={handleAddComment}
                      disabled={!newComment.trim() || submittingComment}
                      className="ml-auto rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {submittingComment ? '…' : 'Add'}
                    </button>
                  </div>
                </div>

                {/* Comments list */}
                <div className="flex-1 overflow-y-auto p-3 space-y-3">
                  {comments.length === 0 ? (
                    <p className="text-center text-xs text-gray-400 py-4">No comments yet</p>
                  ) : (
                    comments.map((c) => {
                      const cfg = commentTypeConfig[c.comment_type as CommentType] || commentTypeConfig.comment;
                      return (
                        <div
                          key={c.id}
                          className={`rounded-lg border p-3 text-sm ${
                            c.resolved ? 'border-gray-200 bg-gray-50 opacity-60' : 'border-gray-200 bg-white'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${cfg.color}`}>
                              {cfg.icon} {cfg.label}
                            </span>
                            <div className="flex items-center gap-1">
                              {c.page_number && (
                                <button
                                  onClick={() => goToPage(c.page_number!)}
                                  className="text-[10px] text-blue-600 hover:underline"
                                  title="Go to page"
                                >
                                  p.{c.page_number}
                                </button>
                              )}
                              <button
                                onClick={() => handleToggleResolved(c)}
                                className="text-[10px] text-gray-400 hover:text-green-600"
                                title={c.resolved ? 'Mark unresolved' : 'Mark resolved'}
                              >
                                {c.resolved ? '↩' : '✓'}
                              </button>
                              <button
                                onClick={() => handleDeleteComment(c.id)}
                                className="text-[10px] text-gray-400 hover:text-red-600"
                                title="Delete"
                              >
                                ✕
                              </button>
                            </div>
                          </div>

                          {editingCommentId === c.id ? (
                            <div className="mt-1 space-y-1">
                              <textarea
                                value={editingContent}
                                onChange={(e) => setEditingContent(e.target.value)}
                                rows={2}
                                className="w-full rounded border px-2 py-1 text-xs resize-none"
                              />
                              <div className="flex gap-1">
                                <button
                                  onClick={() => handleUpdateComment(c.id)}
                                  className="rounded bg-blue-600 px-2 py-0.5 text-[10px] text-white"
                                >
                                  Save
                                </button>
                                <button
                                  onClick={() => setEditingCommentId(null)}
                                  className="rounded bg-gray-200 px-2 py-0.5 text-[10px]"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <p
                              className="text-gray-700 text-xs cursor-pointer"
                              onDoubleClick={() => {
                                setEditingCommentId(c.id);
                                setEditingContent(c.content);
                              }}
                            >
                              {c.content}
                            </p>
                          )}

                          {c.highlight_text && (
                            <p className="mt-1 rounded bg-yellow-50 border border-yellow-200 px-2 py-1 text-[10px] text-yellow-800 italic">
                              &ldquo;{c.highlight_text}&rdquo;
                            </p>
                          )}

                          <p className="mt-1 text-[10px] text-gray-400">
                            {c.author_name || 'Admin'} · {new Date(c.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ── Comments Tab (full view) ──────────────────────────── */}
          {activeTab === 'comments' && (
            <div className="space-y-6">
              {/* Add comment form */}
              <div className="rounded-xl border bg-white p-6">
                <h3 className="font-semibold text-gray-900 mb-4">Add Comment / Highlight</h3>
                <div className="space-y-4">
                  <textarea
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    placeholder="Write your comment, note, or highlight description..."
                    rows={3}
                    className="w-full rounded-lg border border-gray-200 px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <div className="flex flex-wrap items-center gap-3">
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Type</label>
                      <select
                        value={commentType}
                        onChange={(e) => setCommentType(e.target.value as CommentType)}
                        className="rounded-lg border px-3 py-2 text-sm"
                      >
                        <option value="comment">💬 Comment</option>
                        <option value="highlight">🖍️ Highlight</option>
                        <option value="issue">⚠️ Issue</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Page (optional)</label>
                      <input
                        type="number"
                        value={commentPage}
                        onChange={(e) => setCommentPage(e.target.value)}
                        placeholder="e.g., 3"
                        min={1}
                        className="w-20 rounded-lg border px-3 py-2 text-sm"
                      />
                    </div>
                    {commentType === 'highlight' && (
                      <div className="flex-1 min-w-[200px]">
                        <label className="block text-xs text-gray-500 mb-1">Highlighted text</label>
                        <input
                          type="text"
                          value={highlightText}
                          onChange={(e) => setHighlightText(e.target.value)}
                          placeholder="Paste the text you're highlighting..."
                          className="w-full rounded-lg border px-3 py-2 text-sm"
                        />
                      </div>
                    )}
                    <div className="ml-auto self-end">
                      <button
                        onClick={handleAddComment}
                        disabled={!newComment.trim() || submittingComment}
                        className="rounded-lg bg-blue-600 px-6 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
                      >
                        {submittingComment ? 'Adding…' : 'Add Comment'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Comments list */}
              {comments.length === 0 ? (
                <div className="rounded-xl border bg-white p-8 text-center text-gray-500">
                  No comments yet. Add your first comment above.
                </div>
              ) : (
                <div className="space-y-3">
                  {comments.map((c) => {
                    const cfg = commentTypeConfig[c.comment_type as CommentType] || commentTypeConfig.comment;
                    return (
                      <div
                        key={c.id}
                        className={`rounded-xl border p-5 ${
                          c.resolved ? 'border-gray-200 bg-gray-50' : 'border-gray-200 bg-white'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.color}`}>
                              {cfg.icon} {cfg.label}
                            </span>
                            {c.page_number && (
                              <button
                                onClick={() => { setActiveTab('preview'); setTimeout(() => goToPage(c.page_number!), 100); }}
                                className="text-xs text-blue-600 hover:underline"
                              >
                                📄 Page {c.page_number}
                              </button>
                            )}
                            {c.resolved && (
                              <span className="text-xs text-green-600">✓ Resolved</span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleToggleResolved(c)}
                              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                                c.resolved
                                  ? 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200'
                                  : 'bg-green-100 text-green-800 hover:bg-green-200'
                              }`}
                            >
                              {c.resolved ? 'Reopen' : 'Resolve'}
                            </button>
                            <button
                              onClick={() => {
                                setEditingCommentId(c.id);
                                setEditingContent(c.content);
                              }}
                              className="rounded px-2 py-1 text-xs font-medium bg-gray-100 text-gray-700 hover:bg-gray-200"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDeleteComment(c.id)}
                              className="rounded px-2 py-1 text-xs font-medium bg-red-50 text-red-700 hover:bg-red-100"
                            >
                              Delete
                            </button>
                          </div>
                        </div>

                        {editingCommentId === c.id ? (
                          <div className="space-y-2">
                            <textarea
                              value={editingContent}
                              onChange={(e) => setEditingContent(e.target.value)}
                              rows={3}
                              className="w-full rounded-lg border px-3 py-2 text-sm resize-none"
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={() => handleUpdateComment(c.id)}
                                className="rounded bg-blue-600 px-4 py-1.5 text-xs font-medium text-white"
                              >
                                Save
                              </button>
                              <button
                                onClick={() => setEditingCommentId(null)}
                                className="rounded bg-gray-200 px-4 py-1.5 text-xs font-medium"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <p className="text-sm text-gray-700 whitespace-pre-wrap">{c.content}</p>
                        )}

                        {c.highlight_text && (
                          <div className="mt-2 rounded-lg bg-yellow-50 border border-yellow-200 px-3 py-2">
                            <p className="text-xs text-yellow-800 italic">&ldquo;{c.highlight_text}&rdquo;</p>
                          </div>
                        )}

                        <p className="mt-2 text-xs text-gray-400">
                          {c.author_name || 'Admin'} · {new Date(c.created_at).toLocaleString()}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ── Details Tab ───────────────────────────────────────── */}
          {activeTab === 'details' && (
            <div className="grid gap-6 lg:grid-cols-2">
              {/* Document info card */}
              <div className="rounded-xl border bg-white p-6">
                <h3 className="font-semibold text-gray-900 mb-4">Document Information</h3>
                <dl className="space-y-3">
                  {[
                    ['Filename', doc.filename],
                    ['Subject', doc.subject],
                    ['Level', doc.level],
                    ['Year', doc.year],
                    ['Category', categoryInfo ? `${categoryInfo.icon} ${categoryInfo.label}` : doc.document_category],
                    ['Pages', doc.page_count ? String(doc.page_count) : 'Unknown'],
                    ['Duration', doc.official_duration_minutes ? `${doc.official_duration_minutes} minutes` : 'Not set'],
                    ['Uploaded', new Date(doc.created_at).toLocaleString()],
                    ['Status', doc.ingestion_status],
                  ].map(([label, value]) => (
                    <div key={label} className="flex justify-between text-sm">
                      <dt className="text-gray-500">{label}</dt>
                      <dd className="text-gray-900 font-medium text-right max-w-[60%] truncate">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              {/* Ownership & access */}
              <div className="rounded-xl border bg-white p-6">
                <h3 className="font-semibold text-gray-900 mb-4">Ownership & Access</h3>
                <dl className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">Uploaded by</dt>
                    <dd className="text-gray-900 font-medium">
                      {doc.uploader_name || doc.uploaded_by}
                    </dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">Type</dt>
                    <dd className="text-gray-900 font-medium">
                      {doc.is_personal ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-purple-100 px-2.5 py-0.5 text-xs text-purple-800">
                          👤 Student Upload
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs text-blue-800">
                          🏫 Official
                        </span>
                      )}
                    </dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">Shared</dt>
                    <dd className="text-gray-900 font-medium">{doc.is_shared ? 'Yes' : 'No'}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">Archived</dt>
                    <dd className="text-gray-900 font-medium">
                      {doc.is_archived ? (
                        <span className="text-amber-700">Yes</span>
                      ) : (
                        'No'
                      )}
                    </dd>
                  </div>
                  {doc.is_archived && doc.archive_reason && (
                    <div className="flex justify-between text-sm">
                      <dt className="text-gray-500">Archive reason</dt>
                      <dd className="text-gray-900 font-medium text-right max-w-[60%]">
                        {doc.archive_reason}
                      </dd>
                    </div>
                  )}
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">Comments</dt>
                    <dd className="text-gray-900 font-medium">{doc.comment_count || 0}</dd>
                  </div>
                  <div className="flex justify-between text-sm">
                    <dt className="text-gray-500">Ingestion</dt>
                    <dd>
                      <span
                        className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                          doc.ingestion_status === 'completed'
                            ? 'bg-green-100 text-green-800'
                            : doc.ingestion_status === 'failed'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-yellow-100 text-yellow-800'
                        }`}
                      >
                        {doc.ingestion_status}
                      </span>
                    </dd>
                  </div>
                </dl>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="text-center py-12 text-gray-500">Document not found</div>
      )}

      {/* ── Archive Modal ─────────────────────────────────────────── */}
      {showArchiveModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setShowArchiveModal(false); }}
        >
          <div className="w-full max-w-md rounded-xl bg-white shadow-2xl p-6">
            <h3 className="text-lg font-bold text-gray-900 mb-2">🗄 Archive Document</h3>
            <p className="text-sm text-gray-600 mb-4">
              {doc?.is_personal
                ? 'This document was uploaded by a student. Archiving will hide it from their library.'
                : 'Archiving will hide this document from students. It can be restored later.'}
            </p>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Reason {doc?.is_personal && <span className="text-red-500">*</span>}
              </label>
              <textarea
                value={archiveReason}
                onChange={(e) => setArchiveReason(e.target.value)}
                placeholder={
                  doc?.is_personal
                    ? 'e.g., Duplicate content, inappropriate material, wrong subject...'
                    : 'Optional reason for archiving...'
                }
                rows={3}
                className="w-full rounded-lg border border-gray-200 px-4 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowArchiveModal(false)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleArchive}
                disabled={archiving || (doc?.is_personal && !archiveReason.trim())}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
              >
                {archiving ? 'Archiving…' : 'Archive'}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
