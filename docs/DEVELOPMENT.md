# Frontend Development & Deployment

## Prerequisites

- Node.js 20+ and npm
- Running backend on http://localhost:8000
- Running RAG service on http://localhost:8001

## Setup

```bash
# 1. Install dependencies
npm install

# 2. Create environment file
cp .env.local.example .env.local

# 3. Update .env.local if needed (default localhost works for dev)
```

## Development

```bash
# Start Next.js dev server on http://localhost:3000
npm run dev

# Run linter
npm run lint

# Format code
npm run format

# Run tests
npm test
```

## Project Structure

```
app/
  ├── (auth)/              ← Auth routes group
  │   ├── login/           ← POST /api/users/login
  │   └── register/        ← POST /api/users/register
  ├── admin/               ← Admin-only routes
  │   ├── documents/       ← POST /api/documents/ (upload)
  │   ├── students/        ← GET /api/progress/ (aggregate)
  │   └── analytics/       ← Future: system-wide analytics
  ├── student/             ← Student-only routes
  │   ├── practice/        ← POST /api/quiz/generate (3 modes)
  │   ├── progress/        ← GET /api/progress/
  │   ├── attempts/        ← GET /api/attempts/
  │   └── quiz/[id]/       ← GET /api/quiz/{id} (in progress)
  ├── dashboard/           ← Authenticated dashboard (role check)
  ├── page.tsx             ← Public home page
  ├── layout.tsx           ← Root layout with Providers
  └── providers.tsx        ← SWR + other client providers
lib/
  ├── api/
  │   ├── client.ts        ← Axios instance with auth interceptors
  │   ├── endpoints.ts     ← API functions (authAPI, documentAPI, etc.)
  │   └── index.ts         ← Exports
  ├── hooks/
  │   └── index.ts         ← useAuth, useDocuments, useQuiz, etc.
  ├── stores/
  │   └── auth.ts          ← Zustand auth state (persisted)
  └── types.ts             ← TypeScript interfaces (match backend)
config/
  └── constants.ts         ← Routes, API endpoints, education levels
```

## Integration Points with Backend

### Authentication Flow
1. User enters email/password on `/register` or `/login`
2. Frontend calls `POST /api/users/register` or `POST /api/users/login`
3. Backend returns `AuthResponse { access_token, token_type, user }`
4. Frontend stores token via `apiClient.setToken()` and user in Zustand store
5. Zustand `persist` middleware saves to localStorage
6. On page load: Zustand hydrates, sets `hasHydrated=true`
7. `AuthGuard` component waits for `hasHydrated` before checking `isAuthenticated`
8. All subsequent requests include `Authorization: Bearer {token}`
9. 401 response -> Axios interceptor clears Zustand store -> redirect to `/login`

### Quiz Generation
1. Student on `/student/practice` clicks quiz mode
2. Frontend calls `POST /api/quiz/generate` with mode + optional topic/count
3. Backend queries Progress table for weak topics (if adaptive mode)
4. Backend calls RAG service to fetch questions matching filters
5. Backend creates Quiz + QuizQuestion records
6. Frontend navigates to `/student/quiz/{quiz_id}`

### Document Upload
1. Admin on `/admin/documents` fills form + selects PDF
2. Frontend calls `POST /api/documents/` with FormData (multipart/form-data)
3. Backend saves file to `uploads/` directory
4. Backend creates Document record with status = PENDING
5. Backend queues Celery task `ingest_document(doc_id, file_path)`
6. Celery worker calls RAG service `/ingest/`
7. RAG: OCR -> chunk -> embed -> build VectorStoreIndex -> persist to disk
8. Celery updates Document status -> COMPLETED
9. Frontend polls document list to see status updates (via SWR revalidation)

### Progress Tracking
1. Student submits quiz on `/student/quiz/{id}`
2. Frontend calls `POST /api/attempts/` with answers + duration
3. Backend grades all answers
4. Backend calculates per-topic accuracy
5. Backend updates Progress table (upserts per student+topic)
6. Backend returns AttemptRead with topic breakdown
7. Frontend navigates to results view
8. Student clicks `/student/progress` to see aggregated metrics

## Key Features

### SWR Integration
- All `GET` endpoints use SWR for automatic caching & revalidation
- Example: `useDocuments()` uses SWR to auto-fetch `/api/documents/`
- Deduping: same request within 60s uses cached result
- Focus revalidation disabled for better UX

### Error Handling
- API client catches 401 → clears token + redirects to login
- Form errors shown in-place with red alert boxes
- API errors mapped to user-friendly messages
- Network errors handled gracefully

### Auth State Persistence
- Zustand store with localStorage persistence
- On page reload, auth state restored from localStorage
- `useAuth()` provides `fetchCurrentUser()` to sync with backend
- Used in `RootLayout` or each page's `useEffect` to initialize

### Responsive Design
- TailwindCSS with mobile-first breakpoints (sm, md, lg)
- Grid layouts that stack on mobile
- Form inputs optimized for touch

## Testing

Run tests with `npm test`. Test suites verify:
- API client configuration
- Auth store initialization
- Hook imports
- Type definitions
- Constants defined correctly

Extend tests to:
- Mock SWR + test data fetching
- Test form submissions
- Test error handling
- Test auth redirects

## Deployment

### Vercel (Recommended for Next.js)
```bash
npm install -g vercel
vercel
# Follow prompts to link repo + deploy
```

### Docker
See root `Dockerfile` for frontend (or create one):
```dockerfile
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app/.next .next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./
RUN npm ci --only=production
EXPOSE 3000
CMD ["npm", "start"]
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API URL |
| `NEXT_PUBLIC_RAG_URL` | `http://localhost:8001` | RAG service URL (optional) |

## Common Issues

### "fetch failed" on API calls
- Ensure backend is running on correct URL
- Check CORS settings in backend (should allow `localhost:3000`)
- Verify `NEXT_PUBLIC_API_URL` env var is set

### Auth token not persisting
- Check localStorage in DevTools (Application tab)
- Verify Zustand persist middleware is configured
- Check `ACCESS_TOKEN_KEY` constant in `config/constants.ts`

### SWR not updating after form submit
- Call `mutate()` returned from hook after submit
- Example: `const { documents, mutate } = useDocuments(); await upload(...); await mutate();`

### Quiz timer not starting
- Ensure `official_duration_minutes` from backend is valid
- Quiz timer component needs to be implemented in `/student/quiz/[id]/page.tsx`
