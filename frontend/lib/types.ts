/**
 * TypeScript types matching backend schemas (pydantic models).
 * Keep in sync with backend/app/schemas/
 */

export type Role = 'student' | 'admin';
export type EducationLevel = 'P6' | 'S3' | 'S6' | 'TTC';
export type QuizMode = 'adaptive' | 'topic-focused' | 'real-exam';
export type IngestionStatus = 'pending' | 'ingesting' | 'completed' | 'failed';

// ── User & Auth ────────────────────────────────────────────────────────────

export interface UserCreate {
  email: string;
  password: string;
  full_name: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface UserRead {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface AuthResponse {
  user: UserRead;
  access_token: string;
}

// ── Documents ──────────────────────────────────────────────────────────────

export interface DocumentCreate {
  subject: string;
  level: EducationLevel;
  year: string;
  official_duration_minutes?: number;
  instructions?: string;
}

export interface DocumentRead extends DocumentCreate {
  id: string;
  filename: string;
  file_path: string;
  ingestion_status: IngestionStatus;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
  uploaded_by: string;
}

// ── Topics ────────────────────────────────────────────────────────────────

export interface TopicRead {
  id: string;
  name: string;
  description?: string;
  parent_topic_id?: string;
  created_at: string;
}

// ── Quiz & Questions ──────────────────────────────────────────────────────

export interface QuestionRead {
  id: string;
  text: string;
  topic?: string;
  subtopic?: string;
  difficulty?: string;
  options?: string[];
  question_type: string;
  source_document?: string;
}

export interface QuizGenerateRequest {
  mode: QuizMode;
  topics?: string[];
  level?: EducationLevel;
  difficulty?: string;
  count?: number;
}

export interface QuizRead {
  id: string;
  mode: QuizMode;
  duration_minutes?: number;
  instructions?: string;
  questions: QuestionRead[];
  question_count: number;
  created_at: string;
}

// ── Attempts & Submissions ────────────────────────────────────────────────

export interface AttemptSubmit {
  quiz_id: string;
  answers: Record<string, string>; // {question_id: answer_text}
}

export interface TopicScore {
  topic: string;
  correct: number;
  total: number;
  accuracy: number;
}

export interface AttemptRead {
  id: string;
  quiz_id: string;
  student_id: string;
  score: number;
  total: number;
  percentage: number;
  topic_breakdown: TopicScore[];
  started_at: string;
  submitted_at?: string;
}

export interface AttemptAnswerRead {
  question_id: string;
  question_text: string;
  student_answer: string;
  correct_answer?: string;
  is_correct?: boolean;
  topic?: string;
  options?: string[];
}

export interface AttemptDetailRead extends AttemptRead {
  answers: AttemptAnswerRead[];
}

// ── AI Review ─────────────────────────────────────────────────────────────

export interface AIReviewResponse {
  explanation: string;
  sources: Array<{ rank?: number; score?: number; content: string; metadata?: Record<string, unknown> }>;
}

// ── Progress & Analytics ──────────────────────────────────────────────────

export interface TopicMetric {
  topic: string;
  accuracy: number;
  attempts: number;
  last_attempted?: string;
}

export interface ProgressRead {
  student_id: string;
  overall_accuracy: number;
  total_attempts: number;
  topic_metrics: TopicMetric[];
  weak_topics: string[];
  recommendations: string[];
  last_attempt_at?: string;
}

// ── Admin Dashboard ───────────────────────────────────────────────────────

export interface StudentSummary {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
  total_attempts: number;
  overall_accuracy: number;
  last_attempt_at: string | null;
}

export interface StudentAttemptSummary {
  id: string;
  score: number;
  total: number;
  percentage: number;
  started_at: string;
  submitted_at: string | null;
}

export interface StudentDetail extends StudentSummary {
  topic_metrics: TopicMetric[];
  weak_topics: string[];
  recent_attempts: StudentAttemptSummary[];
}

export interface SystemOverview {
  total_students: number;
  total_admins: number;
  total_documents: number;
  total_questions: number;
  total_quizzes: number;
  total_attempts: number;
  avg_accuracy: number;
  active_students_7d: number;
  active_students_30d: number;
}

export interface SubjectStat {
  subject: string;
  document_count: number;
  question_count: number;
  attempt_count: number;
  avg_accuracy: number;
}

export interface TrendPoint {
  date: string;
  attempts: number;
  avg_accuracy: number;
  active_students: number;
}

export interface TopicStat {
  topic: string;
  total_attempts: number;
  avg_accuracy: number;
  student_count: number;
}

export interface RecentAttempt {
  id: string;
  student_name: string;
  score: number;
  total: number;
  percentage: number;
  submitted_at: string | null;
}

export interface AnalyticsResponse {
  overview: SystemOverview;
  subject_stats: SubjectStat[];
  trends: TrendPoint[];
  topic_stats: TopicStat[];
  recent_attempts: RecentAttempt[];
}

// ── API Responses ──────────────────────────────────────────────────────────

export interface ErrorResponse {
  success: false;
  error_code: string;
  message: string;
  details?: Record<string, any>;
}

export interface SuccessResponse<T = any> {
  success: true;
  data: T;
}

export type ApiResponse<T> = SuccessResponse<T> | ErrorResponse;

// ── Pagination ────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

// ── Chat Sessions ─────────────────────────────────────────────────────────

export interface ChatSessionRead {
  id: string;
  collection: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessageRead {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{ rank: number; score: number; content: string; metadata: Record<string, unknown> }>;
  created_at: string;
}

export interface ChatSessionDetail extends ChatSessionRead {
  messages: ChatMessageRead[];
}
