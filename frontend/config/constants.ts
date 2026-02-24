/**
 * Configuration constants and environment variables.
 */

export const API_URL = process.env.NEXT_PUBLIC_API_URL || '';
export const RAG_URL = process.env.NEXT_PUBLIC_RAG_URL || 'http://localhost:8001';

export const ROUTES = {
  // Auth
  LOGIN: '/login',
  REGISTER: '/register',
  LOGOUT: '/logout',

  // Dashboard
  DASHBOARD: '/dashboard',

  // Student routes
  STUDENT_PRACTICE: '/student/practice',
  STUDENT_PROGRESS: '/student/progress',
  STUDENT_ATTEMPTS: '/student/attempts',
  STUDENT_ATTEMPT_DETAIL: (id: string) => `/student/attempts/${id}`,
  STUDENT_BROWSE: '/student/browse',
  STUDENT_ASK_AI: '/student/ask-ai',
  STUDENT_DOCUMENTS: '/student/documents',
  STUDENT_PROFILE: '/student/profile',

  // Admin routes
  ADMIN_DOCUMENTS: '/admin/documents',
  ADMIN_STUDENTS: '/admin/students',
  ADMIN_ANALYTICS: '/admin/analytics',
};

// ── API Endpoints ────────────────────────────────────────────────────────

export const API_ENDPOINTS = {
  // Auth
  REGISTER: '/api/users/register',
  LOGIN: '/api/users/login',
  ME: '/api/users/me',
  UPDATE_ME: '/api/users/me',

  // Documents
  DOCUMENTS: '/api/documents/',
  DOCUMENT_DETAIL: (id: string) => `/api/documents/${id}`,

  // Quiz
  QUIZ_GENERATE: '/api/quiz/generate',
  QUIZ_DETAIL: (id: string) => `/api/quiz/${id}`,

  // Attempts
  ATTEMPTS: '/api/attempts/',
  ATTEMPT_DETAIL: (id: string) => `/api/attempts/${id}`,
  ATTEMPT_REVIEW: (id: string) => `/api/attempts/${id}/review`,
  ATTEMPT_QUESTION_EXPLAIN: (attemptId: string, questionId: string) =>
    `/api/attempts/${attemptId}/questions/${questionId}/explain`,

  // Progress
  PROGRESS: '/api/progress/',

  // RAG
  RAG_QUERY: '/api/rag/query',
  RAG_RETRIEVE: '/api/rag/retrieve',

  // Chat
  CHAT_SESSIONS: '/api/chat/sessions',
  CHAT_SESSION_DETAIL: (id: string) => `/api/chat/sessions/${id}`,
  CHAT_SESSION_MESSAGES: (id: string) => `/api/chat/sessions/${id}/messages`,

  // Health
  HEALTH: '/health',

  // Admin
  ADMIN_STUDENTS_LIST: '/api/admin/students',
  ADMIN_STUDENT_DETAIL: (id: string) => `/api/admin/students/${id}`,
  ADMIN_ANALYTICS: '/api/admin/analytics',
  ADMIN_STUDENT_PERFORMANCE: (id: string) => `/api/admin/students/${id}/performance`,
  ADMIN_WEAK_TOPICS: '/api/admin/students/weak-topics/summary',

  // Documents (split into admin and student upload endpoints)
  DOCUMENTS_ADMIN: '/api/documents/admin',
  DOCUMENTS_STUDENT: '/api/documents/student',
  DOCUMENT_SHARE: (id: string) => `/api/documents/${id}/share`,
  DOCUMENT_UNSHARE: (docId: string, studentId: string) => `/api/documents/${docId}/share/${studentId}`,
};

// ── Constants ────────────────────────────────────────────────────────────

export const EDUCATION_LEVELS = [
  { value: 'P6', label: 'Primary 6 (P6)' },
  { value: 'S3', label: 'Ordinary Level (S3)' },
  { value: 'S6', label: 'Advanced Level (S6)' },
  { value: 'TTC', label: 'Teacher Training (TTC)' },
] as const;

export const QUIZ_MODES = [
  {
    value: 'adaptive',
    label: 'Adaptive Practice',
    description: 'Practice weak topics based on your performance history',
  },
  {
    value: 'topic-focused',
    label: 'Topic-Focused',
    description: 'Practice random questions in a specific topic',
  },
  {
    value: 'real-exam',
    label: 'Real Exam Simulation',
    description: 'Full-length exam with official timing',
  },
] as const;

export const QUESTION_TYPES = ['multiple-choice', 'short-answer', 'essay'] as const;

// ── Thresholds & Config ────────────────────────────────────────────────

export const WEAK_TOPIC_THRESHOLD = 0.60; // 60% accuracy
export const ACCESS_TOKEN_KEY = 'e_exam_access_token';
export const USER_KEY = 'e_exam_user';

// ── Pagination defaults ────────────────────────────────────────────────

export const DEFAULT_PAGE_SIZE = 20;
export const DEFAULT_LIMIT = 50;
