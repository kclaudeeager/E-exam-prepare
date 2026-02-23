# Frontend Guide

Next.js 14 frontend for E-exam-prepare with role-based dashboards, exam practice interface, and progress analytics.

## 📁 Structure

```
frontend/
├── app/                    # Next.js app router
│   ├── (auth)/            # Authentication routes (login, register)
│   ├── (student)/         # Student routes with layout
│   │   ├── dashboard/     # Practice dashboard, quiz selection
│   │   ├── exam-practice/ # Timed exam interface
│   │   └── progress/      # Score history, analytics
│   ├── (admin)/           # Admin routes with layout
│   │   ├── dashboard/     # Student progress overview
│   │   └── documents/     # Document management & curation
│   ├── api/               # API routes (avoid - use backend instead)
│   └── layout.tsx         # Root layout
├── components/
│   ├── auth/              # Login, register, role selection
│   ├── exam/              # Question renderer, timer, submission
│   ├── quiz/              # Quiz controls, score display
│   ├── documents/         # Upload, file management
│   ├── progress/          # Charts, analytics, recommendations
│   └── shared/            # Navbar, sidebar, buttons, modals
├── hooks/                 # Custom React hooks
│   ├── useExamQuiz.ts     # Quiz API logic
│   ├── useDocumentUpload.ts
│   ├── useProgress.ts
│   └── useAuth.ts
├── lib/
│   ├── api-client.ts      # Fetch wrapper, error handling
│   ├── types.ts           # TypeScript interfaces (shared with backend)
│   ├── constants.ts       # Quiz modes, education levels, subjects
│   └── utils.ts           # Helpers
├── styles/
│   └── globals.css        # TailwindCSS imports
├── next.config.js
├── tsconfig.json
├── tailwind.config.ts
├── package.json
└── README.md
```

## 🎨 Key Components

### `useExamQuiz` Hook
Handles quiz state, timer, submission:
```typescript
const { 
  quiz, 
  currentQuestion, 
  timeRemaining, 
  answers, 
  setAnswer, 
  submit 
} = useExamQuiz("adaptive", { topics: ["Geometry"] });
```

### `ExamPractice` Component
Full-screen timed exam interface with:
- Question rendering (text, images, MCQ)
- Countdown timer with warnings
- Progress indicator
- Submit button

### `ProgressDashboard` Component
Shows:
- Per-topic accuracy bar charts
- Weak topic recommendations
- Improvement trends
- Attempt history

## 🔐 Authentication

Uses `next-auth` with role-based routes:
- Redirect unauthorized students to login
- Load student/admin specific UI
- Persist session

## 🌍 Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=E-exam-prepare
NEXTAUTH_SECRET=<generate-with-openssl>
NEXTAUTH_URL=http://localhost:3000
```

## 📦 Dependencies

```json
{
  "next": "^14.0.0",
  "react": "^18.2.0",
  "typescript": "^5.0.0",
  "tailwindcss": "^3.3.0",
  "next-auth": "^4.24.0",
  "swr": "^2.2.0",
  "recharts": "^2.10.0",
  "zustand": "^4.4.0"
}
```

## 🚀 Development

```bash
npm run dev          # Start dev server
npm run build        # Production build
npm run lint         # ESLint
npm run format       # Prettier
npm run test         # Jest tests
```

## 📝 Coding Patterns

### Data Fetching with SWR
```typescript
// hooks/useExamQuiz.ts
import useSWR from 'swr';

export function useExamQuiz(mode: 'adaptive' | 'topic-focused' | 'real-exam', options?: QuizOptions) {
  const { data, error, mutate } = useSWR(
    `/api/quiz/generate?mode=${mode}`,
    fetcher,
    { revalidateOnFocus: false }
  );
  
  return { quiz: data, loading: !data && !error, error, mutate };
}
```

### Custom Hooks for State Management
Isolate business logic from UI:
```typescript
const [answers, setAnswers] = useState<Record<string, string>>({});
const [submitted, setSubmitted] = useState(false);

const submitAnswers = async () => {
  const result = await fetch('/api/attempts', {
    method: 'POST',
    body: JSON.stringify({ quizId, answers })
  });
  setSubmitted(true);
};
```

## 🎯 Routes

### Student Routes (Protected)
- `/student/dashboard` - Quiz mode selection
- `/student/exam-practice/:quizId` - Timed exam
- `/student/progress` - Score history & analytics

### Admin Routes (Protected)
- `/admin/dashboard` - Student metrics overview
- `/admin/documents` - Upload & manage documents
- `/admin/students/:id/progress` - Individual student analytics

### Auth Routes
- `/auth/login` - Login form
- `/auth/register` - Registration
- `/auth/role-select` - Student/Admin choice
