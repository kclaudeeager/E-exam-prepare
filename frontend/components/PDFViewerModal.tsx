'use client';

import { useState, useEffect, useCallback } from 'react';
import { ACCESS_TOKEN_KEY, API_ENDPOINTS } from '@/config/constants';

interface PDFViewerModalProps {
  /** Document ID to fetch the PDF */
  documentId: string;
  /** Display filename */
  filename?: string;
  /** Extra subtitle info (subject, year, etc.) */
  subtitle?: string;
  /** Initial page to navigate to (1-based) */
  initialPage?: number;
  /** Total pages if known (enables page input) */
  totalPages?: number;
  /** Close handler */
  onClose: () => void;
}

/**
 * Shared PDF viewer modal with page navigation.
 * Fetches the PDF with Bearer token auth and displays in an iframe.
 * Uses #page=N fragment for page navigation.
 */
export default function PDFViewerModal({
  documentId,
  filename,
  subtitle,
  initialPage,
  totalPages,
  onClose,
}: PDFViewerModalProps) {
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [currentPage, setCurrentPage] = useState(initialPage ?? 1);
  const [pageInput, setPageInput] = useState(String(initialPage ?? 1));

  // Fetch the PDF with auth
  useEffect(() => {
    let revoke: string | null = null;
    let cancelled = false;

    async function loadPdf() {
      setLoading(true);
      setError('');

      try {
        const token =
          typeof window !== 'undefined'
            ? localStorage.getItem(ACCESS_TOKEN_KEY)
            : null;
        if (!token) throw new Error('Not authenticated. Please sign in again.');

        const res = await fetch(API_ENDPOINTS.DOCUMENT_PDF(documentId), {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          let detail = 'Failed to load PDF';
          try {
            const data = await res.json();
            detail = data?.detail || detail;
          } catch {
            /* ignore */
          }
          throw new Error(detail);
        }

        const blob = await res.blob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        revoke = url;
        setPdfBlobUrl(url);
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load PDF');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadPdf();

    return () => {
      cancelled = true;
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [documentId]);

  // Build the iframe URL with page fragment
  const iframeSrc = pdfBlobUrl ? `${pdfBlobUrl}#page=${currentPage}` : '';

  const goToPage = useCallback(
    (page: number) => {
      const p = Math.max(1, totalPages ? Math.min(page, totalPages) : page);
      setCurrentPage(p);
      setPageInput(String(p));
    },
    [totalPages],
  );

  const handlePageInputSubmit = () => {
    const p = parseInt(pageInput, 10);
    if (!isNaN(p) && p >= 1) goToPage(p);
  };

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative flex flex-col bg-white rounded-xl shadow-2xl w-full max-w-5xl h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-gray-900 truncate">
              {filename || 'Document'}
            </h3>
            {subtitle && (
              <p className="text-xs text-gray-500 truncate">{subtitle}</p>
            )}
          </div>

          {/* Page navigation controls */}
          <div className="flex items-center gap-2 mx-4">
            <button
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage <= 1}
              className="rounded-md bg-gray-100 px-2 py-1 text-sm font-medium text-gray-700 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Previous page"
            >
              ← Prev
            </button>

            <div className="flex items-center gap-1 text-sm text-gray-600">
              <span>Page</span>
              <input
                type="text"
                value={pageInput}
                onChange={(e) => setPageInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handlePageInputSubmit();
                }}
                onBlur={handlePageInputSubmit}
                className="w-12 rounded border border-gray-300 px-1.5 py-0.5 text-center text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              {totalPages && <span>of {totalPages}</span>}
            </div>

            <button
              onClick={() => goToPage(currentPage + 1)}
              disabled={totalPages ? currentPage >= totalPages : false}
              className="rounded-md bg-gray-100 px-2 py-1 text-sm font-medium text-gray-700 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="Next page"
            >
              Next →
            </button>
          </div>

          <button
            onClick={onClose}
            className="shrink-0 rounded-lg bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
          >
            ✕ Close
          </button>
        </div>

        {/* PDF content */}
        <div className="flex-1 overflow-hidden">
          {loading && (
            <div className="flex h-full items-center justify-center text-sm text-gray-500 gap-2">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600" />
              Loading PDF...
            </div>
          )}
          {!loading && error && (
            <div className="flex h-full items-center justify-center px-6 text-center text-sm text-red-600">
              {error}
            </div>
          )}
          {!loading && !error && pdfBlobUrl && (
            <iframe
              key={`${pdfBlobUrl}#page=${currentPage}`}
              src={iframeSrc}
              className="w-full h-full border-0"
              title={filename || 'PDF Document'}
            />
          )}
        </div>

        {/* Footer with page highlight hint */}
        {initialPage && initialPage > 1 && (
          <div className="border-t bg-blue-50 px-4 py-2 text-xs text-blue-700 text-center">
            📌 Opened at <strong>page {initialPage}</strong> from source reference
          </div>
        )}
      </div>
    </div>
  );
}
