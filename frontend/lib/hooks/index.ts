/**
 * Custom React hooks for auth, documents, quiz, attempts, progress.
 */

import { useCallback } from 'react';
import useSWR, { SWRConfiguration } from 'swr';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/stores/auth';
import { authAPI, documentAPI, quizAPI, attemptAPI, progressAPI, apiClient } from '@/lib/api';
import {
  UserCreate,
  UserLogin,
  DocumentRead,
  QuizGenerateRequest,
  QuizRead,
  AttemptSubmit,
  AttemptRead,
  ProgressRead,
} from '@/lib/types';
import { API_ENDPOINTS } from '@/config/constants';

// ── useAuth Hook ──────────────────────────────────────────────────────────

export const useAuth = () => {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, setUser, setLoading, logout, hasRole } = useAuthStore();

  const register = useCallback(
    async (data: UserCreate) => {
      setLoading(true);
      try {
        const response = await authAPI.register(data);
        apiClient.setToken(response.access_token);
        setUser(response.user);
        router.push('/dashboard');
        return { success: true };
      } catch (error: any) {
        return {
          success: false,
          error: error.response?.data?.message || 'Registration failed',
        };
      } finally {
        setLoading(false);
      }
    },
    [router, setUser, setLoading],
  );

  const login = useCallback(
    async (data: UserLogin) => {
      setLoading(true);
      try {
        const response = await authAPI.login(data);
        apiClient.setToken(response.access_token);
        setUser(response.user);
        router.push('/dashboard');
        return { success: true };
      } catch (error: any) {
        return {
          success: false,
          error: error.response?.data?.message || 'Login failed',
        };
      } finally {
        setLoading(false);
      }
    },
    [router, setUser, setLoading],
  );

  const handleLogout = useCallback(() => {
    logout();
    router.push('/login');
  }, [router, logout]);

  const fetchCurrentUser = useCallback(async () => {
    try {
      const data = await authAPI.getMe();
      setUser(data);
      return data;
    } catch (error) {
      logout();
      return null;
    }
  }, [setUser, logout]);

  return {
    user,
    isAuthenticated,
    isLoading,
    register,
    login,
    logout: handleLogout,
    fetchCurrentUser,
    hasRole,
  };
};

// ── useDocuments Hook ─────────────────────────────────────────────────────

export const useDocuments = (subject?: string, level?: string, swrConfig?: SWRConfiguration) => {
  const { data: documents, error, isLoading, mutate } = useSWR<DocumentRead[]>(
    [API_ENDPOINTS.DOCUMENTS, subject, level],
    () => documentAPI.list(subject, level),
    swrConfig,
  );

  const upload = useCallback(
    async (file: File, metadata: any) => {
      try {
        const doc = await documentAPI.upload(file, metadata);
        await mutate();
        return { success: true, data: doc };
      } catch (error: any) {
        return {
          success: false,
          error: error.response?.data?.message || 'Upload failed',
        };
      }
    },
    [mutate],
  );

  return {
    documents: documents || [],
    isLoading,
    error,
    upload,
    mutate,
  };
};

// ── useQuiz Hook ──────────────────────────────────────────────────────────

export const useQuiz = () => {
  const generate = useCallback(async (request: QuizGenerateRequest) => {
    try {
      const quiz = await quizAPI.generate(request);
      return { success: true, data: quiz };
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.message || 'Failed to generate quiz',
      };
    }
  }, []);

  const { data: quiz, error, isLoading } = useSWR<QuizRead>(
    null, // quiz ID passed manually
    null,
  );

  const getQuiz = useCallback(async (id: string) => {
    try {
      const data = await quizAPI.get(id);
      return { success: true, data };
    } catch (error: any) {
      return {
        success: false,
        error: error.response?.data?.message || 'Failed to fetch quiz',
      };
    }
  }, []);

  return {
    quiz,
    isLoading,
    error,
    generate,
    getQuiz,
  };
};

// ── useAttempts Hook ──────────────────────────────────────────────────────

export const useAttempts = (swrConfig?: SWRConfiguration) => {
  const { data: attempts, error, isLoading, mutate } = useSWR<AttemptRead[]>(
    API_ENDPOINTS.ATTEMPTS,
    () => attemptAPI.list(),
    swrConfig,
  );

  const submit = useCallback(
    async (data: AttemptSubmit) => {
      try {
        const attempt = await attemptAPI.submit(data);
        await mutate();
        return { success: true, data: attempt };
      } catch (error: any) {
        return {
          success: false,
          error: error.response?.data?.message || 'Failed to submit attempt',
        };
      }
    },
    [mutate],
  );

  return {
    attempts: attempts || [],
    isLoading,
    error,
    submit,
    mutate,
  };
};

// ── useProgress Hook ──────────────────────────────────────────────────────

export const useProgress = (swrConfig?: SWRConfiguration) => {
  const { data: progress, error, isLoading, mutate } = useSWR<ProgressRead>(
    API_ENDPOINTS.PROGRESS,
    () => progressAPI.get(),
    swrConfig,
  );

  return {
    progress,
    isLoading,
    error,
    mutate,
  };
};
