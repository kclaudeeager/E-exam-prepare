'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/hooks';
import { documentAPI } from '@/lib/api';
import { DocumentRead } from '@/lib/types';
import { EDUCATION_LEVELS } from '@/config/constants';

const LEVEL_LABELS: Record<string, string> = Object.fromEntries(
  EDUCATION_LEVELS.map(({ value, label }) => [value, label]),
);

const STATUS_BADGE: Record<
  string,
  { label: string; className: string }
> = {
  pending: {
    label: '⏳ Pending',
    className: 'bg-yellow-100 text-yellow-700',
  },
  processing: {
    label: '⚙️ Processing',
    className: 'bg-blue-100 text-blue-700',
  },
  completed: {
    label: '✅ Ready',
    className: 'bg-green-100 text-green-700',
  },
  failed: {
    label: '❌ Failed',
    className: 'bg-red-100 text-red-700',
  },
};

export default function StudentDocumentsPage() {
  const router = useRouter();
  const { user, isAuthenticated, fetchCurrentUser } = useAuth();

  const [documents, setDocuments] = useState<DocumentRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Upload form state
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadMeta, setUploadMeta] = useState({
    subject: '',
    level: '',
    year: String(new Date().getFullYear()),
    official_duration_minutes: '',
  });

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
      router.push('/dashboard');
      return;
    }
    loadDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const loadDocuments = async () => {
    setLoading(true);
    setError('');
    try {
      const all = await documentAPI.list();
      // Show only personal docs the student uploaded themselves
      setDocuments(all.filter((d) => d.is_personal));
    } catch {
      setError('Failed to load your documents. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setUploadError('Please select a PDF file.');
      return;
    }
    if (!uploadMeta.subject || !uploadMeta.level || !uploadMeta.year) {
      setUploadError('Subject, level, and year are required.');
      return;
    }

    setUploading(true);
    setUploadError('');
    setUploadSuccess('');
    try {
      await documentAPI.uploadStudent(file, {
        subject: uploadMeta.subject,
        level: uploadMeta.level,
        year: uploadMeta.year,
        official_duration_minutes: uploadMeta.official_duration_minutes
          ? Number(uploadMeta.official_duration_minutes)
          : undefined,
      });
      setUploadSuccess('Document uploaded! It will be ready after processing.');
      setUploadMeta({
        subject: '',
        level: '',
        year: String(new Date().getFullYear()),
        official_duration_minutes: '',
      });
      if (fileRef.current) fileRef.current.value = '';
      setShowUpload(false);
      await loadDocuments();
    } catch {
      setUploadError('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const handleMetaChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
  ) => {
    setUploadMeta((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  if (loading && !documents.length) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading your documents…</p>
      </div>
    );
  }

  return (
    <main className="container py-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">My Documents</h1>
          <p className="text-sm text-gray-500 mt-1">
            Upload your own study materials and use them in practice quizzes.
          </p>
        </div>
        <button
          onClick={() => {
            setShowUpload((v) => !v);
            setUploadError('');
            setUploadSuccess('');
          }}
          className="mt-3 sm:mt-0 btn-primary px-4 py-2 self-start"
        >
          {showUpload ? '✕ Cancel' : '＋ Upload Document'}
        </button>
      </div>

      {/* Global success/error */}
      {uploadSuccess && !showUpload && (
        <div className="mb-4 rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
          ✅ {uploadSuccess}
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Upload form */}
      {showUpload && (
        <form
          onSubmit={handleUpload}
          className="mb-6 rounded-lg border bg-white p-5 shadow-sm space-y-4"
        >
          <h2 className="font-semibold text-gray-900">Upload New Document</h2>

          {uploadError && (
            <div className="rounded-md bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">
              {uploadError}
            </div>
          )}

          {/* File */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-700">
              PDF File <span className="text-red-500">*</span>
            </label>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="block w-full text-sm text-gray-500 file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {/* Subject */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">
                Subject <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="subject"
                value={uploadMeta.subject}
                onChange={handleMetaChange}
                placeholder="e.g. Mathematics"
                className="input"
                required
              />
            </div>

            {/* Level */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">
                Level <span className="text-red-500">*</span>
              </label>
              <select
                name="level"
                value={uploadMeta.level}
                onChange={handleMetaChange}
                className="input"
                required
              >
                <option value="">— Select level —</option>
                {EDUCATION_LEVELS.map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>

            {/* Year */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">
                Year <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                name="year"
                value={uploadMeta.year}
                onChange={handleMetaChange}
                placeholder="e.g. 2023"
                className="input"
                required
              />
            </div>

            {/* Duration */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-gray-700">
                Duration (minutes)
              </label>
              <input
                type="number"
                name="official_duration_minutes"
                value={uploadMeta.official_duration_minutes}
                onChange={handleMetaChange}
                placeholder="e.g. 120"
                min={1}
                className="input"
              />
            </div>
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="submit"
              disabled={uploading}
              className="btn-primary px-5 py-2 disabled:opacity-60"
            >
              {uploading ? 'Uploading…' : 'Upload'}
            </button>
            <button
              type="button"
              onClick={() => setShowUpload(false)}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Document list */}
      {documents.length === 0 ? (
        <div className="rounded-lg border bg-white p-12 text-center">
          <div className="text-4xl mb-3">📂</div>
          <p className="text-gray-600 font-medium">No personal documents yet</p>
          <p className="text-sm text-gray-400 mt-1">
            Upload a PDF to get started with personalised practice.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {documents.map((doc) => {
            const badge = STATUS_BADGE[doc.ingestion_status] ?? {
              label: doc.ingestion_status,
              className: 'bg-gray-100 text-gray-600',
            };
            return (
              <div key={doc.id} className="card flex flex-col gap-3">
                {/* Title row */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-semibold text-gray-900">
                      {doc.subject}
                    </h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {LEVEL_LABELS[doc.level] ?? doc.level} · {doc.year}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${badge.className}`}
                  >
                    {badge.label}
                  </span>
                </div>

                {/* Duration */}
                {doc.official_duration_minutes && (
                  <p className="text-xs text-gray-500">
                    ⏱{' '}
                    {Math.floor(doc.official_duration_minutes / 60)}h
                    {doc.official_duration_minutes % 60 > 0
                      ? ` ${doc.official_duration_minutes % 60}min`
                      : ''}{' '}
                    duration
                  </p>
                )}

                {/* Filename */}
                <p className="truncate text-xs text-gray-400" title={doc.filename}>
                  📄 {doc.filename}
                </p>

                {/* Actions */}
                <div className="mt-auto flex gap-2">
                  <a
                    href={`/student/practice?document_id=${doc.id}&subject=${encodeURIComponent(doc.subject)}&level=${doc.level}`}
                    className={`flex-1 rounded-md border px-3 py-1.5 text-center text-sm font-medium transition-colors ${
                      doc.ingestion_status === 'completed'
                        ? 'border-blue-600 bg-blue-600 text-white hover:bg-blue-700'
                        : 'border-gray-200 bg-gray-50 text-gray-400 pointer-events-none'
                    }`}
                  >
                    ✏️ Practice
                  </a>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
