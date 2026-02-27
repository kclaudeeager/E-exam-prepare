'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth, useSubjects } from '@/lib/hooks';
import { subjectAPI } from '@/lib/api';
import { SubjectRead } from '@/lib/types';
import { ROUTES, EDUCATION_LEVELS } from '@/config/constants';

export default function AdminSubjectsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [filterLevel, setFilterLevel] = useState<string>('');
  const { subjects, isLoading, mutate } = useSubjects(filterLevel || undefined);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newLevel, setNewLevel] = useState('');
  const [newIcon, setNewIcon] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [creating, setCreating] = useState(false);

  // Seeding state
  const [seeding, setSeeding] = useState(false);

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Auth guard
  useEffect(() => {
    if (user && user.role !== 'admin') {
      router.push(ROUTES.DASHBOARD);
    }
  }, [user, router]);

  const clearMessages = () => { setError(''); setSuccess(''); };

  const handleSeedDefaults = async () => {
    clearMessages();
    setSeeding(true);
    try {
      await subjectAPI.seedDefaults();
      setSuccess('Default subjects seeded successfully!');
      mutate();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to seed defaults');
    } finally {
      setSeeding(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName || !newLevel) {
      setError('Name and level are required');
      return;
    }
    clearMessages();
    setCreating(true);
    try {
      await subjectAPI.create({
        name: newName,
        level: newLevel as any,
        icon: newIcon || undefined,
        description: newDescription || undefined,
      });
      setSuccess(`Subject "${newName}" created!`);
      setNewName('');
      setNewLevel('');
      setNewIcon('');
      setNewDescription('');
      setShowCreate(false);
      mutate();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create subject');
    } finally {
      setCreating(false);
    }
  };

  if (!user || user.role !== 'admin') return null;

  // Group subjects by level
  const groupedByLevel: Record<string, SubjectRead[]> = {};
  for (const s of subjects) {
    const level = s.level || 'Unknown';
    if (!groupedByLevel[level]) groupedByLevel[level] = [];
    groupedByLevel[level].push(s);
  }

  const levelOrder = EDUCATION_LEVELS.map((l) => l.value as string);
  const sortedLevels = Object.keys(groupedByLevel).sort(
    (a, b) => (levelOrder.indexOf(a) === -1 ? 999 : levelOrder.indexOf(a)) -
              (levelOrder.indexOf(b) === -1 ? 999 : levelOrder.indexOf(b))
  );

  return (
    <main className="container py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📚 Subject Management</h1>
          <p className="text-sm text-gray-500">
            Manage subjects for all education levels. Students enroll in subjects to access related documents.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-blue-50 px-4 py-2 text-center">
            <p className="text-2xl font-bold text-blue-600">{subjects.length}</p>
            <p className="text-xs text-blue-600/70">Total Subjects</p>
          </div>
        </div>
      </div>

      {/* Action bar */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={filterLevel}
          onChange={(e) => { clearMessages(); setFilterLevel(e.target.value); }}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="">All levels</option>
          {EDUCATION_LEVELS.map((l) => (
            <option key={l.value} value={l.value}>{l.label}</option>
          ))}
        </select>

        <button
          onClick={() => { clearMessages(); setShowCreate(!showCreate); }}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
        >
          {showCreate ? '✕ Cancel' : '+ New Subject'}
        </button>

        <button
          onClick={handleSeedDefaults}
          disabled={seeding}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          {seeding ? '⏳ Seeding…' : '🌱 Seed All Defaults'}
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          {success}
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="rounded-xl border bg-white p-6 shadow-sm space-y-4">
          <h3 className="font-semibold text-gray-900">Create New Subject</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Subject Name *</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g., Defensive Driving"
                required
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Education Level *</label>
              <select
                value={newLevel}
                onChange={(e) => setNewLevel(e.target.value)}
                required
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              >
                <option value="">Select level</option>
                {EDUCATION_LEVELS.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Icon (emoji)</label>
              <input
                type="text"
                value={newIcon}
                onChange={(e) => setNewIcon(e.target.value)}
                placeholder="e.g., 🛡️"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <input
                type="text"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="Optional description"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={creating}
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? 'Creating…' : 'Create Subject'}
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="rounded-lg border border-gray-300 px-5 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Subjects list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
        </div>
      ) : subjects.length === 0 ? (
        <div className="rounded-xl border bg-white p-12 text-center">
          <div className="text-4xl mb-3">📚</div>
          <p className="text-gray-600 font-medium">No subjects found</p>
          <p className="text-sm text-gray-400 mt-1">
            {filterLevel
              ? `No subjects for level "${filterLevel}". Try seeding defaults.`
              : 'Click "Seed All Defaults" to create subjects for all levels.'}
          </p>
        </div>
      ) : filterLevel ? (
        /* Flat list when filtering a specific level */
        <div className="rounded-xl border bg-white shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Subject</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-600">Level</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Documents</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-600">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {subjects.map((s) => (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">{s.icon || '📖'}</span>
                        <div>
                          <p className="font-medium text-gray-900">{s.name}</p>
                          {s.description && (
                            <p className="text-xs text-gray-500 line-clamp-1">{s.description}</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                        {s.level}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`font-medium ${s.document_count > 0 ? 'text-green-600' : 'text-gray-400'}`}>
                        {s.document_count}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-gray-500">
                      {new Date(s.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Grouped view when showing all levels */
        <div className="space-y-6">
          {sortedLevels.map((level) => {
            const levelSubjects = groupedByLevel[level];
            const levelInfo = EDUCATION_LEVELS.find((l) => l.value === level);
            const totalDocs = levelSubjects.reduce((sum, s) => sum + s.document_count, 0);

            return (
              <div key={level} className="rounded-xl border bg-white shadow-sm overflow-hidden">
                <div className="flex items-center justify-between border-b bg-gray-50 px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-semibold text-blue-700">
                      {levelInfo?.label || level}
                    </span>
                    <span className="text-sm text-gray-500">
                      {levelSubjects.length} subject{levelSubjects.length !== 1 ? 's' : ''}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>{totalDocs} doc{totalDocs !== 1 ? 's' : ''} total</span>
                  </div>
                </div>
                <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
                  {levelSubjects.map((s) => (
                    <div
                      key={s.id}
                      className="flex items-center gap-3 rounded-lg border border-gray-100 bg-gray-50/50 p-3 hover:border-blue-200 hover:bg-blue-50/30 transition-colors"
                    >
                      <span className="text-2xl">{s.icon || '📖'}</span>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 truncate">{s.name}</p>
                        <p className="text-xs text-gray-500">
                          {s.document_count} doc{s.document_count !== 1 ? 's' : ''}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </main>
  );
}
