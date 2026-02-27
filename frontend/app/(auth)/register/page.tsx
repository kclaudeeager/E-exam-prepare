'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/hooks';
import { UserCreate, AccountType, EducationLevel } from '@/lib/types';
import { ROUTES, ACCOUNT_TYPES, ACADEMIC_LEVELS, PRACTICE_CATEGORIES } from '@/config/constants';

export default function RegisterPage() {
  const { register, isLoading } = useAuth();
  const [formData, setFormData] = useState<UserCreate>({
    email: '',
    password: '',
    full_name: '',
    account_type: undefined,
    education_level: undefined,
  });
  const [error, setError] = useState<string>('');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value || undefined }));
  };

  const handleAccountType = (type: AccountType) => {
    setFormData((prev) => ({
      ...prev,
      account_type: type,
      // Reset education_level when switching purpose
      education_level: undefined,
    }));
  };

  const handlePracticeCategory = (level: EducationLevel) => {
    setFormData((prev) => ({ ...prev, education_level: level }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!formData.email || !formData.password || !formData.full_name) {
      setError('All fields are required');
      return;
    }

    const result = await register(formData);
    if (!result.success) {
      setError(result.error || 'Registration failed');
    }
  };

  return (
    <div className="flex-center min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="card w-full max-w-md shadow-lg">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-gray-900">Create Account</h1>
          <p className="mt-2 text-gray-600">Join E-exam-prepare today</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="full_name" className="block text-sm font-medium text-gray-700">
              Full Name
            </label>
            <input
              type="text"
              id="full_name"
              name="full_name"
              value={formData.full_name}
              onChange={handleChange}
              placeholder="John Doe"
              disabled={isLoading}
              className="mt-1 w-full"
            />
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
              Email
            </label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="you@example.com"
              disabled={isLoading}
              className="mt-1 w-full"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="••••••••"
              disabled={isLoading}
              className="mt-1 w-full"
            />
          </div>

          {/* Purpose selector — Academic vs Practice */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              What are you preparing for?
            </label>
            <div className="grid grid-cols-2 gap-3">
              {ACCOUNT_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => handleAccountType(t.value as AccountType)}
                  disabled={isLoading}
                  className={`flex flex-col items-center gap-1 rounded-xl border-2 p-3 text-center transition-all ${
                    formData.account_type === t.value
                      ? 'border-blue-500 bg-blue-50 shadow-sm'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <span className="text-2xl">{t.icon}</span>
                  <span className="text-sm font-semibold text-gray-800">{t.label}</span>
                  <span className="text-xs text-gray-500 leading-tight">{t.description}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Academic: show education levels */}
          {formData.account_type === 'academic' && (
            <div>
              <label htmlFor="education_level" className="block text-sm font-medium text-gray-700">
                Education Level
              </label>
              <select
                id="education_level"
                name="education_level"
                value={formData.education_level || ''}
                onChange={handleChange}
                disabled={isLoading}
                className="mt-1 w-full"
              >
                <option value="">Select your level (optional)</option>
                {ACADEMIC_LEVELS.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>
          )}

          {/* Practice: show practice categories */}
          {formData.account_type === 'practice' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Choose your practice area
              </label>
              <div className="space-y-2">
                {PRACTICE_CATEGORIES.map((cat) => (
                  <button
                    key={cat.value}
                    type="button"
                    onClick={() => handlePracticeCategory(cat.value as EducationLevel)}
                    disabled={isLoading}
                    className={`flex w-full items-center gap-3 rounded-lg border-2 px-4 py-3 text-left transition-all ${
                      formData.education_level === cat.value
                        ? 'border-blue-500 bg-blue-50 shadow-sm'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <span className="text-2xl">{cat.icon}</span>
                    <div>
                      <span className="text-sm font-semibold text-gray-800">{cat.label}</span>
                      <p className="text-xs text-gray-500">{cat.description}</p>
                    </div>
                  </button>
                ))}
                <p className="text-xs text-gray-400 mt-1">
                  More practice areas coming soon — nursing, security guard, etc.
                </p>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-blue-600 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {isLoading ? 'Creating...' : 'Create Account'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-600">
          Already have an account?{' '}
          <Link href={ROUTES.LOGIN} className="font-medium text-blue-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
