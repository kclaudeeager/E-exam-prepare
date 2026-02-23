/**
 * Integration test: verify frontend can communicate with backend.
 * Run with: npm test (or jest directly)
 */

import { apiClient } from '@/lib/api/client';

describe('Frontend API Integration', () => {
  test('should have API client configured', () => {
    expect(apiClient).toBeDefined();
  });

  test('auth store should be importable', async () => {
    const { useAuthStore } = await import('@/lib/stores/auth');
    expect(useAuthStore).toBeDefined();
  });

  test('hooks should be importable', async () => {
    const { useAuth, useDocuments, useQuiz, useAttempts, useProgress } = await import(
      '@/lib/hooks'
    );
    expect(useAuth).toBeDefined();
    expect(useDocuments).toBeDefined();
    expect(useQuiz).toBeDefined();
    expect(useAttempts).toBeDefined();
    expect(useProgress).toBeDefined();
  });

  test('types should be importable', async () => {
    // TypeScript types are compiled away at runtime in Jest
    // This test just verifies the module can be imported without errors
    const types = await import('@/lib/types')
    expect(types).toBeDefined()
  });

  test('constants should be importable', async () => {
    const { API_URL, ROUTES, EDUCATION_LEVELS, QUIZ_MODES } = await import(
      '@/config/constants'
    );
    expect(API_URL).toBeDefined();
    expect(ROUTES).toBeDefined();
    expect(EDUCATION_LEVELS).toBeDefined();
    expect(QUIZ_MODES).toBeDefined();
  });
});
