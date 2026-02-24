/**
 * API endpoint functions wrapping the HTTP client.
 * Organized by feature (auth, documents, quiz, attempts, progress).
 */

import { apiClient } from './client';
import { API_ENDPOINTS } from '@/config/constants';
import {
  UserCreate,
  UserLogin,
  UserUpdate,
  AuthResponse,
  UserRead,
  DocumentRead,
  DocumentShareRequest,
  DocumentShareResponse,
  QuizGenerateRequest,
  QuizRead,
  AttemptSubmit,
  AttemptRead,
  AttemptDetailRead,
  AIReviewResponse,
  ProgressRead,
  ChatSessionRead,
  ChatSessionDetail,
  ChatMessageRead,
  StudentSummary,
  StudentDetail,
  AnalyticsResponse,
  StudentPerformanceTrend,
  WeakTopicsSummary,
} from '@/lib/types';

// ── Auth ───────────────────────────────────────────────────────────────────

export const authAPI = {
  register: async (data: UserCreate) => {
    const response = await apiClient.post<AuthResponse>(
      API_ENDPOINTS.REGISTER,
      data,
    );
    return response.data;
  },

  login: async (data: UserLogin) => {
    const response = await apiClient.post<AuthResponse>(
      API_ENDPOINTS.LOGIN,
      data,
    );
    return response.data;
  },

  getMe: async () => {
    const response = await apiClient.get<UserRead>(API_ENDPOINTS.ME);
    return response.data;
  },

  updateProfile: async (data: UserUpdate) => {
    const response = await apiClient.patch<UserRead>(
      API_ENDPOINTS.UPDATE_ME,
      data,
    );
    return response.data;
  },

  logout: () => {
    apiClient.clearToken();
  },
};

// ── Documents ──────────────────────────────────────────────────────────────

type DocUploadMeta = {
  subject: string;
  level: string;
  year: string;
  official_duration_minutes?: number;
  instructions?: string;
};

function buildDocFormData(file: File, metadata: DocUploadMeta): FormData {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('subject', metadata.subject);
  formData.append('level', metadata.level);
  formData.append('year', metadata.year);
  if (metadata.official_duration_minutes) {
    formData.append('official_duration_minutes', String(metadata.official_duration_minutes));
  }
  if (metadata.instructions) {
    formData.append('instructions', metadata.instructions);
  }
  return formData;
}

export const documentAPI = {
  /** Admin: upload a level-designated exam paper */
  uploadAdmin: async (file: File, metadata: DocUploadMeta): Promise<DocumentRead> => {
    const response = await apiClient.postFormData<DocumentRead>(
      API_ENDPOINTS.DOCUMENTS_ADMIN,
      buildDocFormData(file, metadata),
    );
    return response.data;
  },

  /** Student: upload a personal document */
  uploadStudent: async (file: File, metadata: DocUploadMeta): Promise<DocumentRead> => {
    const response = await apiClient.postFormData<DocumentRead>(
      API_ENDPOINTS.DOCUMENTS_STUDENT,
      buildDocFormData(file, metadata),
    );
    return response.data;
  },

  list: async (subject?: string, level?: string, skip = 0, limit = 50, includeArchived = false): Promise<DocumentRead[]> => {
    const params = new URLSearchParams();
    if (subject) params.append('subject', subject);
    if (level) params.append('level', level);
    params.append('skip', String(skip));
    params.append('limit', String(limit));
    if (includeArchived) params.append('include_archived', 'true');
    const response = await apiClient.get<DocumentRead[]>(
      `${API_ENDPOINTS.DOCUMENTS}?${params.toString()}`,
    );
    return response.data;
  },

  get: async (id: string): Promise<DocumentRead> => {
    const response = await apiClient.get<DocumentRead>(API_ENDPOINTS.DOCUMENT_DETAIL(id));
    return response.data;
  },

  archive: async (id: string): Promise<DocumentRead> => {
    const response = await apiClient.patch<DocumentRead>(`${API_ENDPOINTS.DOCUMENT_DETAIL(id)}/archive`);
    return response.data;
  },

  restore: async (id: string): Promise<DocumentRead> => {
    const response = await apiClient.patch<DocumentRead>(`${API_ENDPOINTS.DOCUMENT_DETAIL(id)}/restore`);
    return response.data;
  },

  share: async (id: string, studentIds: string[]): Promise<DocumentShareResponse> => {
    const body: DocumentShareRequest = { student_ids: studentIds };
    const response = await apiClient.post<DocumentShareResponse>(
      API_ENDPOINTS.DOCUMENT_SHARE(id),
      body,
    );
    return response.data;
  },

  unshare: async (docId: string, studentId: string): Promise<void> => {
    await apiClient.delete(API_ENDPOINTS.DOCUMENT_UNSHARE(docId, studentId));
  },
};

// ── Quiz ───────────────────────────────────────────────────────────────────

export const quizAPI = {
  generate: async (request: QuizGenerateRequest) => {
    const response = await apiClient.post<QuizRead>(
      API_ENDPOINTS.QUIZ_GENERATE,
      request,
    );
    return response.data;
  },

  get: async (id: string) => {
    const response = await apiClient.get<QuizRead>(
      API_ENDPOINTS.QUIZ_DETAIL(id),
    );
    return response.data;
  },
};

// ── Attempts ───────────────────────────────────────────────────────────────

export const attemptAPI = {
  submit: async (data: AttemptSubmit) => {
    const response = await apiClient.post<AttemptRead>(
      API_ENDPOINTS.ATTEMPTS,
      data,
    );
    return response.data;
  },

  list: async (skip = 0, limit = 50) => {
    const params = new URLSearchParams();
    params.append('skip', String(skip));
    params.append('limit', String(limit));

    const response = await apiClient.get<AttemptRead[]>(
      `${API_ENDPOINTS.ATTEMPTS}?${params.toString()}`,
    );
    return response.data;
  },

  get: async (id: string) => {
    const response = await apiClient.get<AttemptDetailRead>(
      API_ENDPOINTS.ATTEMPT_DETAIL(id),
    );
    return response.data;
  },

  reviewWithAI: async (attemptId: string, question?: string) => {
    const response = await apiClient.post<AIReviewResponse>(
      API_ENDPOINTS.ATTEMPT_REVIEW(attemptId),
      question ? { question } : {},
    );
    return response.data;
  },

  explainQuestion: async (attemptId: string, questionId: string, question?: string) => {
    const response = await apiClient.post<AIReviewResponse>(
      API_ENDPOINTS.ATTEMPT_QUESTION_EXPLAIN(attemptId, questionId),
      question ? { question } : {},
    );
    return response.data;
  },
};

// ── Progress ───────────────────────────────────────────────────────────────

export const progressAPI = {
  get: async () => {
    const response = await apiClient.get<ProgressRead>(API_ENDPOINTS.PROGRESS);
    return response.data;
  },
};

// ── RAG ────────────────────────────────────────────────────────────────────

export interface RAGQueryResponse {
  answer: string;
  sources: Array<{ rank: number; score: number; content: string; metadata: Record<string, unknown> }>;
  graph_enhanced: boolean;
}

export interface RAGRetrieveResponse {
  results: Array<{ rank: number; score: number; content: string; metadata: Record<string, unknown> }>;
  graph_paths: Array<unknown>;
}

export const ragAPI = {
  query: async (
    question: string,
    collection = 'General',
    top_k = 5,
    chat_history?: Array<{ role: string; content: string }>,
  ): Promise<RAGQueryResponse> => {
    const payload: Record<string, unknown> = { question, collection, top_k };
    if (chat_history && chat_history.length > 0) {
      payload.chat_history = chat_history;
    }
    const response = await apiClient.post<RAGQueryResponse>(
      API_ENDPOINTS.RAG_QUERY,
      payload,
    );
    return response.data;
  },

  retrieve: async (query: string, collection = 'General', top_k = 10): Promise<RAGRetrieveResponse> => {
    const response = await apiClient.post<RAGRetrieveResponse>(
      API_ENDPOINTS.RAG_RETRIEVE,
      { query, collection, top_k },
    );
    return response.data;
  },
};

// ── Chat Sessions ──────────────────────────────────────────────────────────

export const chatAPI = {
  createSession: async (collection: string, title?: string): Promise<ChatSessionRead> => {
    const response = await apiClient.post<ChatSessionRead>(
      API_ENDPOINTS.CHAT_SESSIONS,
      { collection, title: title || 'New Chat' },
    );
    return response.data;
  },

  listSessions: async (collection?: string): Promise<ChatSessionRead[]> => {
    const params = collection ? `?collection=${encodeURIComponent(collection)}` : '';
    const response = await apiClient.get<ChatSessionRead[]>(
      `${API_ENDPOINTS.CHAT_SESSIONS}${params}`,
    );
    return response.data;
  },

  getSession: async (id: string): Promise<ChatSessionDetail> => {
    const response = await apiClient.get<ChatSessionDetail>(
      API_ENDPOINTS.CHAT_SESSION_DETAIL(id),
    );
    return response.data;
  },

  deleteSession: async (id: string): Promise<void> => {
    await apiClient.delete(API_ENDPOINTS.CHAT_SESSION_DETAIL(id));
  },

  addMessage: async (
    sessionId: string,
    role: string,
    content: string,
    sources?: Array<Record<string, unknown>>,
  ): Promise<ChatMessageRead> => {
    const response = await apiClient.post<ChatMessageRead>(
      API_ENDPOINTS.CHAT_SESSION_MESSAGES(sessionId),
      { role, content, sources },
    );
    return response.data;
  },
};

// ── Health ────────────────────────────────────────────────────────────────

export const healthAPI = {
  check: async () => {
    const response = await apiClient.get(API_ENDPOINTS.HEALTH);
    return response.data;
  },
};

// ── Admin ─────────────────────────────────────────────────────────────────

export const adminAPI = {
  listStudents: async (search?: string, skip = 0, limit = 50): Promise<StudentSummary[]> => {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    params.append('skip', String(skip));
    params.append('limit', String(limit));
    const response = await apiClient.get<StudentSummary[]>(
      `${API_ENDPOINTS.ADMIN_STUDENTS_LIST}?${params.toString()}`,
    );
    return response.data;
  },

  getStudent: async (id: string): Promise<StudentDetail> => {
    const response = await apiClient.get<StudentDetail>(
      API_ENDPOINTS.ADMIN_STUDENT_DETAIL(id),
    );
    return response.data;
  },

  getAnalytics: async (days = 30): Promise<AnalyticsResponse> => {
    const response = await apiClient.get<AnalyticsResponse>(
      `${API_ENDPOINTS.ADMIN_ANALYTICS}?days=${days}`,
    );
    return response.data;
  },

  getStudentPerformance: async (id: string): Promise<StudentPerformanceTrend> => {
    const response = await apiClient.get<StudentPerformanceTrend>(
      API_ENDPOINTS.ADMIN_STUDENT_PERFORMANCE(id),
    );
    return response.data;
  },

  getWeakTopicsSummary: async (): Promise<WeakTopicsSummary> => {
    const response = await apiClient.get<WeakTopicsSummary>(
      API_ENDPOINTS.ADMIN_WEAK_TOPICS,
    );
    return response.data;
  },
};
