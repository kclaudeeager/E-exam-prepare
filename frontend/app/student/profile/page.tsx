'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/hooks';
import { authAPI } from '@/lib/api';
import { ROUTES, EDUCATION_LEVELS } from '@/config/constants';

const LEVEL_LABELS: Record<string, string> = Object.fromEntries(
  EDUCATION_LEVELS.map(({ value, label }) => [value, label]),
);

export default function StudentProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, fetchCurrentUser } = useAuth();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');

  // Editable fields
  const [fullName, setFullName] = useState('');
  const [educationLevel, setEducationLevel] = useState('');

  useEffect(() => {
    const init = async () => {
      if (!isAuthenticated) {
        await fetchCurrentUser();
      }
      setLoading(false);
    };
    init();
  }, [isAuthenticated, fetchCurrentUser]);

  // Pre-fill form once user is available
  useEffect(() => {
    if (!user) return;
    if (user.role !== 'student') {
      router.push(ROUTES.DASHBOARD);
      return;
    }
    setFullName(user.full_name ?? '');
    setEducationLevel(user.education_level ?? '');
  }, [user, router]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) {
      setError('Full name cannot be empty.');
      return;
    }
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await authAPI.updateProfile({
        full_name: fullName.trim(),
        education_level: (educationLevel as 'P6' | 'S3' | 'S6' | 'TTC') || undefined,
      });
      // Refresh the global user state
      await fetchCurrentUser();
      setSuccess('Profile updated successfully!');
    } catch {
      setError('Failed to save changes. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading profile…</p>
      </div>
    );
  }

  if (!user) return null;

  return (
    <main className="container py-8 max-w-xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">My Profile</h1>
        <p className="text-sm text-gray-500 mt-1">
          View and update your account details.
        </p>
      </div>

      {/* Read-only info card */}
      <div className="card mb-6 space-y-3">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-2xl font-bold text-blue-700">
            {user.full_name.charAt(0).toUpperCase()}
          </div>
          <div>
            <p className="font-semibold text-gray-900">{user.full_name}</p>
            <p className="text-sm text-gray-500">{user.email}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 border-t pt-3 text-sm">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase">Role</p>
            <span className="inline-block mt-0.5 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700 capitalize">
              {user.role}
            </span>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase">
              Education Level
            </p>
            {user.education_level ? (
              <span className="inline-block mt-0.5 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
                {LEVEL_LABELS[user.education_level] ?? user.education_level}
              </span>
            ) : (
              <span className="inline-block mt-0.5 rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-semibold text-yellow-700">
                Not set
              </span>
            )}
          </div>
        </div>
      </div>

      {/* No level warning */}
      {!user.education_level && (
        <div className="mb-5 rounded-md bg-yellow-50 border border-yellow-200 px-4 py-3 text-sm text-yellow-800">
          ⚠️ <strong>Set your education level</strong> so the platform can
          recommend the right exam papers for you.
        </div>
      )}

      {/* Edit form */}
      <form onSubmit={handleSave} className="card space-y-4">
        <h2 className="font-semibold text-gray-900">Edit Profile</h2>

        {success && (
          <div className="rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
            ✅ {success}
          </div>
        )}
        {error && (
          <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex flex-col gap-1">
          <label
            htmlFor="fullName"
            className="text-sm font-medium text-gray-700"
          >
            Full Name
          </label>
          <input
            id="fullName"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="input"
            required
          />
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="educationLevel"
            className="text-sm font-medium text-gray-700"
          >
            Education Level
          </label>
          <select
            id="educationLevel"
            value={educationLevel}
            onChange={(e) => setEducationLevel(e.target.value)}
            className="input"
          >
            <option value="">— Select your level —</option>
            {EDUCATION_LEVELS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-400">
            This determines which admin exam papers are shown to you.
          </p>
        </div>

        <div className="flex gap-3 pt-1">
          <button
            type="submit"
            disabled={saving}
            className="btn-primary px-5 py-2 disabled:opacity-60"
          >
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
        </div>
      </form>
    </main>
  );
}
