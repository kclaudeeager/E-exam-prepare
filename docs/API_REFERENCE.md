# API Reference: New & Updated Endpoints

## Documents API

### Admin: Upload Level-Designated Document
```
POST /api/documents/admin
Content-Type: multipart/form-data

Parameters:
  file: <PDF file>
  subject: string (e.g., "Mathematics")
  level: enum (P6 | S3 | S6 | TTC)
  year: string (e.g., "2024")
  official_duration_minutes: integer (optional)
  instructions: string (optional)

Response: DocumentRead
{
  "id": "uuid",
  "filename": "P6_Mathematics_2024.pdf",
  "subject": "Mathematics",
  "level": "P6",
  "year": "2024",
  "is_personal": false,
  "is_shared": false,
  "uploaded_by": "admin_uuid",
  "created_at": "2026-02-24T10:00:00Z"
}
```

### Student: Upload Personal Document
```
POST /api/documents/student
Content-Type: multipart/form-data

Parameters:
  file: <PDF file>
  subject: string
  level: enum (P6 | S3 | S6 | TTC)
  year: string
  official_duration_minutes: integer (optional)

Response: DocumentRead
{
  "id": "uuid",
  "filename": "my_math_notes.pdf",
  "subject": "Mathematics",
  "level": "P6",
  "is_personal": true,
  "is_shared": false,
  "uploaded_by": "student_uuid",
  "created_at": "2026-02-24T10:00:00Z"
}
```

### List Documents (Student View)
```
GET /api/documents/?subject=Mathematics&level=P6&only_shared=false

Query Parameters:
  subject: string (optional)
  level: enum (optional)
  only_shared: boolean (default: false)
  include_archived: boolean (default: false)
  skip: integer (default: 0)
  limit: integer (default: 50)

Response: DocumentRead[]
```

### Get Single Document
```
GET /api/documents/{document_id}

Response: DocumentRead
```

### Share Document with Students
```
POST /api/documents/{document_id}/share

Request Body:
{
  "student_ids": ["uuid1", "uuid2", "uuid3"]
}

Response: DocumentShareResponse
{
  "document_id": "uuid",
  "shared_count": 2,
  "shared_with": ["uuid1", "uuid2"],
  "message": "Document shared with 2 new student(s)"
}
```

### Unshare Document from Student
```
DELETE /api/documents/{document_id}/share/{student_id}

Response: {"message": "Document unshared successfully"}
```

---

## Quiz API

### Generate Quiz (UPDATED)
```
POST /api/quiz/generate

Request Body:
{
  "mode": "adaptive|topic-focused|real-exam",
  "document_id": "uuid",                    # NEW: Required
  "subject": "Mathematics",                  # NEW: Required
  "topics": ["Algebra", "Geometry"],        # Optional
  "difficulty": "medium",
  "count": 15
}

Response: QuizRead
{
  "id": "uuid",
  "mode": "topic-focused",
  "document_id": "uuid",                    # NEW: Source document
  "duration_minutes": 30,
  "questions": [
    {
      "id": "uuid",
      "text": "What is 2+2?",
      "question_type": "mcq",
      "options": ["3", "4", "5", "6"],
      "source_document": "P6_Mathematics_2024.pdf",  # Document filename
      "topic": "Algebra",
      "difficulty": "easy"
    }
  ],
  "question_count": 15,
  "created_at": "2026-02-24T10:00:00Z"
}
```

---

## User API (Updated)

### Register User (Updated)
```
POST /api/users/register

Request Body:
{
  "email": "student@example.com",
  "password": "securepass123",
  "full_name": "John Doe",
  "education_level": "P6",              # NEW: Optional
  "role": "student"
}

Response: Token
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
```

### Update User Profile (New)
```
PATCH /api/users/me

Request Body:
{
  "full_name": "John Doe",              # Optional
  "education_level": "S3"               # Optional
}

Response: UserRead
{
  "id": "uuid",
  "email": "student@example.com",
  "full_name": "John Doe",
  "role": "student",
  "education_level": "S3",
  "is_active": true,
  "created_at": "2026-02-24T10:00:00Z"
}
```

---

## Admin API (NEW ENDPOINTS)

### Get Student Performance Trend
```
GET /api/admin/students/{student_id}/performance

Response: StudentPerformanceTrend
{
  "student_id": "uuid",
  "student_name": "Alice Johnson",
  "overall_accuracy": 0.72,
  "attempt_count": 25,
  "weak_topics": [
    {
      "topic_name": "Trigonometry",
      "accuracy": 0.45,
      "attempt_count": 8
    },
    {
      "topic_name": "Calculus",
      "accuracy": 0.55,
      "attempt_count": 5
    }
  ],
  "strong_topics": [
    {
      "topic_name": "Algebra",
      "accuracy": 0.88,
      "attempt_count": 12
    }
  ],
  "recent_attempts": [
    {
      "id": "uuid",
      "score": 18,
      "total": 20,
      "percentage": 90.0,
      "document_name": "P6_Mathematics_2024.pdf",
      "submitted_at": "2026-02-24T10:30:00Z"
    }
  ],
  "last_attempted_at": "2026-02-24T10:30:00Z"
}
```

### Get Weak Topics Summary
```
GET /api/admin/students/weak-topics/summary

Response:
{
  "students_needing_help": [
    {
      "student_id": "uuid",
      "student_name": "Alice Johnson",
      "weak_topic_count": 3,
      "weakest_topics": [
        {
          "topic_name": "Trigonometry",
          "accuracy": 0.35
        },
        {
          "topic_name": "Calculus",
          "accuracy": 0.40
        }
      ]
    },
    {
      "student_id": "uuid2",
      "student_name": "Bob Smith",
      "weak_topic_count": 2,
      "weakest_topics": [...]
    }
  ],
  "total_students_with_weak_topics": 42
}
```

---

## Attempts API (Updated)

### Submit Quiz (Updated)
```
POST /api/attempts/

Request Body:
{
  "quiz_id": "uuid",
  "answers": {
    "question_uuid_1": "A",
    "question_uuid_2": "The answer",
    "question_uuid_3": "B"
  }
}

Response: AttemptRead
{
  "id": "uuid",
  "quiz_id": "uuid",
  "student_id": "student_uuid",
  "document_id": "uuid",        # NEW: Source document tracked
  "score": 18,
  "total": 20,
  "percentage": 90.0,
  "submitted_at": "2026-02-24T10:30:00Z",
  "topic_scores": [
    {
      "topic": "Algebra",
      "correct": 10,
      "total": 10,
      "accuracy": 1.0
    },
    {
      "topic": "Geometry",
      "correct": 8,
      "total": 10,
      "accuracy": 0.8
    }
  ]
}
```

---

## Document Visibility Logic

### For Students
```
Visible documents include:
1. Admin-designated documents matching their education_level
2. Their own personal documents (is_personal=true, uploaded_by=self)
3. Documents other students have shared with them
```

### For Admins
```
Visible documents:
- All documents (for management purposes)
```

---

## Example Flow: Student Workflow

### Step 1: Register with Education Level
```bash
POST /api/users/register
{
  "email": "alice@school.com",
  "password": "pass123",
  "full_name": "Alice Johnson",
  "education_level": "P6"
}
```

### Step 2: View Available Documents
```bash
GET /api/documents/
# Returns: Admin P6 documents + personal + shared
```

### Step 3: Upload Personal Document
```bash
POST /api/documents/student
# Upload: my_math_notes.pdf
# is_personal=true, is_shared=false
```

### Step 4: Share with Classmate Bob
```bash
POST /api/documents/{doc_id}/share
{
  "student_ids": ["bob_uuid"]
}
# Bob now sees this document in GET /api/documents/
```

### Step 5: Generate Quiz from Exam Paper
```bash
POST /api/quiz/generate
{
  "mode": "topic-focused",
  "document_id": "{admin_doc_uuid}",
  "subject": "Mathematics",
  "topics": ["Algebra"],
  "count": 10
}
```

### Step 6: Submit Quiz
```bash
POST /api/attempts/
{
  "quiz_id": "{quiz_uuid}",
  "answers": {...}
}
# System updates Progress table per-topic
# Identifies weak topics (accuracy < 60%)
```

### Step 7: Get Personalized Recommendations
```bash
# Frontend logic: Check progress/weak_topics
# Show: "You scored 45% on Geometry. Practice more?"
# Suggest: Next quiz filtered by Geometry topic
```

---

## Example Flow: Admin Workflow

### Step 1: Upload Level-Designated Document
```bash
POST /api/documents/admin
{
  "file": <P6_Mathematics_2024.pdf>,
  "subject": "Mathematics",
  "level": "P6",
  "year": "2024"
}
# Auto-visible to all P6 students
```

### Step 2: Monitor Student Progress
```bash
GET /api/admin/students/{alice_uuid}/performance
# Response: Overall accuracy, weak/strong topics, recent attempts
```

### Step 3: Find Struggling Students
```bash
GET /api/admin/students/weak-topics/summary
# Response: All students with weak topics, sorted by urgency
```

### Step 4: Intervention Plan
```
Identify: Alice (45% on Geometry)
Action: Email recommending more Geometry practice
Follow-up: Check performance in 1 week
```

---

## Data Model Relationships

```
User (1) ──────> (M) Document (uploaded_by)
  │ education_level
  │
  └──> (M) DocumentShare (shared_with_user)
         │
         └──> (1) Document (document_id)

Document (1) ──────> (M) Question (document_id)
  │ is_personal
  │ is_shared
  │
  └──> (M) DocumentShare (document_id)

Quiz (1) ──────> (M) QuizQuestion ──> Question
     │
     └──> (M) Attempt (quiz_id)
              │ document_id (from first question)
              │
              └──> (M) AttemptAnswer ──> Question

Progress: student_id + topic_id (tracks accuracy/attempts per topic)
  - Used to identify weak topics (accuracy < 60%)
  - Updated on every quiz submission
```

---

## Important Notes

1. **Quiz Generation**: Requires both `document_id` AND `subject`
2. **Weak Topics**: Identified as accuracy < WEAK_TOPIC_THRESHOLD (default 60%)
3. **Progress Tracking**: Updated per quiz submission, not per question
4. **Document Visibility**: Role-based and education-level-aware
5. **Performance Analytics**: Real-time (computed on request, can be cached)

---

## Configuration

See `backend/app/config.py`:
```python
WEAK_TOPIC_THRESHOLD = 0.60  # 60% - topics below this are "weak"
```
