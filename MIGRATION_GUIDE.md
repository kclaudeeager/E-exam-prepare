# Database Migration & Deployment Guide

## Pre-Deployment Checklist

- [ ] All code compiles without errors (verified ✅)
- [ ] Tests pass (if applicable)
- [ ] Environment variables configured
- [ ] Backup database (CRITICAL for production)
- [ ] Have rollback plan ready

## Step 1: Backup Database (CRITICAL)

Before running any migrations on production:

```bash
# PostgreSQL backup
pg_dump -U exam_prep -d exam_prep -h localhost -F c -f exam_prep_backup_$(date +%Y%m%d_%H%M%S).dump

# Or with .env credentials:
pg_dump postgresql://exam_prep:exam_prep_dev@localhost:5432/exam_prep \
  -F c -f exam_prep_backup_$(date +%Y%m%d_%H%M%S).dump
```

## Step 2: Review Migration

The auto-generated migration file is located at:
```
backend/alembic/versions/3295efca321d_add_document_sharing_user_education_.py
```

### Changes in Migration:

1. **New Table: document_shares**
   - Tracks which students have documents shared with them
   - Composite unique constraint: (document_id, shared_with_user_id)

2. **New Columns: users table**
   - `education_level`: VARCHAR (P6, S3, S6, TTC) - nullable

3. **New Columns: documents table**
   - `is_personal`: BOOLEAN (default false) - distinguishes admin vs student uploads
   - `is_shared`: BOOLEAN (default false) - tracks if document is shared with anyone

4. **New Column: attempts table**
   - `document_id`: UUID foreign key to documents - nullable

5. **New Indexes**
   - `ix_documents_is_personal` on documents(is_personal)
   - `ix_documents_is_shared` on documents(is_shared)
   - `ix_documents_is_archived` on documents(is_archived) - already exists

## Step 3: Run Migration

### Development Environment
```bash
cd /Users/mac/Documents/Organizations/Personal/E-exam-prepare/backend

# Activate environment (if not already active)
source ../.venv/bin/activate

# Or use uv (recommended):
uv run alembic upgrade head
```

### Production Environment
```bash
cd backend

# Check current migration status
uv run alembic current

# Preview changes (optional)
uv run alembic upgrade --sql head

# Apply migration
uv run alembic upgrade head

# Verify migration succeeded
uv run alembic current
```

## Step 4: Update Application Code

All code changes are already implemented:

### Files Modified (Summary)
- ✅ `backend/app/db/models.py` - Models updated
- ✅ `backend/app/api/documents.py` - Complete rewrite
- ✅ `backend/app/api/quiz.py` - Source-aware generation
- ✅ `backend/app/api/admin.py` - Performance tracking
- ✅ `backend/app/api/attempts.py` - Document source tracking
- ✅ `backend/app/schemas/*.py` - All schemas updated

### Verification
All Python files compile successfully:
```bash
cd backend
uv run python -m py_compile app/api/documents.py app/api/quiz.py app/api/admin.py app/api/attempts.py
uv run python -m py_compile app/schemas/document.py app/schemas/quiz.py app/schemas/user.py app/schemas/admin.py
```

## Step 5: Test New Functionality

### Test 1: Verify Migration Applied
```bash
cd backend
uv run python -c "
from app.db.session import engine
from app.db.models import User, Document, DocumentShare, Attempt
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()

print('✓ Users table:', 'users' in tables)
print('✓ Documents table:', 'documents' in tables)
print('✓ Document shares table:', 'document_shares' in tables)
print('✓ Attempts table:', 'attempts' in tables)

# Check columns
users_cols = [c['name'] for c in inspector.get_columns('users')]
print('✓ Users.education_level:', 'education_level' in users_cols)

documents_cols = [c['name'] for c in inspector.get_columns('documents')]
print('✓ Documents.is_personal:', 'is_personal' in documents_cols)
print('✓ Documents.is_shared:', 'is_shared' in documents_cols)

attempts_cols = [c['name'] for c in inspector.get_columns('attempts')]
print('✓ Attempts.document_id:', 'document_id' in attempts_cols)

print('\n✅ All migrations applied successfully!')
"
```

### Test 2: Create Test Data
```bash
cd backend
uv run python << 'EOF'
from app.db.session import SessionLocal
from app.db.models import User, RoleEnum, EducationLevelEnum
from datetime import datetime

db = SessionLocal()

# Create test admin
admin = User(
    email="admin@test.com",
    hashed_password="fake_hash",
    full_name="Test Admin",
    role=RoleEnum.ADMIN,
)
db.add(admin)

# Create test student with education level
student = User(
    email="student@test.com",
    hashed_password="fake_hash",
    full_name="Test Student",
    role=RoleEnum.STUDENT,
    education_level=EducationLevelEnum.P6,
)
db.add(student)

db.commit()
print("✅ Test users created successfully")
print(f"  Admin: {admin.email} (no education_level)")
print(f"  Student: {student.email} (education_level={student.education_level})")

db.close()
EOF
```

### Test 3: Test API Endpoint (After Server Starts)
```bash
# Terminal 1: Start backend
cd backend
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2: Test endpoints
curl -X POST http://localhost:8000/api/users/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "p6student@test.com",
    "password": "test123",
    "full_name": "P6 Test Student",
    "education_level": "P6"
  }'

# Expected response:
# {"access_token": "...", "token_type": "bearer"}
```

## Step 6: Verify in Database

### Using psql
```bash
# Connect to database
psql postgresql://exam_prep:exam_prep_dev@localhost:5432/exam_prep

# Check tables
\dt document_shares;

# Check columns
\d users;
\d documents;
\d attempts;

# Verify constraints
\d+ document_shares;  # Should show unique constraint

# Sample query
SELECT 
  u.email,
  u.education_level,
  COUNT(d.id) as doc_count
FROM users u
LEFT JOIN documents d ON u.id = d.uploaded_by
GROUP BY u.id, u.email, u.education_level;
```

### Using Python
```bash
cd backend
uv run python << 'EOF'
from app.db.session import SessionLocal
from app.db.models import User, Document, DocumentShare

db = SessionLocal()

# Check user education levels
users = db.query(User).all()
print(f"Total users: {len(users)}")
for u in users[:5]:
    print(f"  - {u.email}: education_level={u.education_level}")

# Check document flags
docs = db.query(Document).all()
print(f"\nTotal documents: {len(docs)}")
for d in docs[:5]:
    print(f"  - {d.filename}: personal={d.is_personal}, shared={d.is_shared}")

# Check document shares
shares = db.query(DocumentShare).all()
print(f"\nTotal document shares: {len(shares)}")
for s in shares[:5]:
    print(f"  - Document {s.document_id} shared with user {s.shared_with_user_id}")

db.close()
EOF
```

## Step 7: Rollback Plan (If Needed)

### Rollback Last Migration
```bash
cd backend

# Check current state
uv run alembic current

# Rollback one migration
uv run alembic downgrade -1

# Verify rollback
uv run alembic current
```

### Restore from Backup (If Major Issues)
```bash
# Restore PostgreSQL from backup
pg_restore -U exam_prep -d exam_prep -h localhost \
  exam_prep_backup_20260224_103000.dump

# Or using full connection string:
pg_restore -U exam_prep -h localhost \
  --dbname=postgresql://exam_prep:exam_prep_dev@localhost:5432/exam_prep \
  exam_prep_backup_20260224_103000.dump
```

## Step 8: Post-Deployment Validation

After deployment:

1. **Check Server Logs**
   ```bash
   # Watch for any migration-related errors
   tail -f backend.log | grep -i "migration\|error"
   ```

2. **Run Health Check**
   ```bash
   curl http://localhost:8000/api/health
   ```

3. **Test Document API**
   ```bash
   # As authenticated student, list documents
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/documents/
   ```

4. **Test Quiz Generation**
   ```bash
   # Generate quiz from a document
   curl -X POST -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/quiz/generate \
     -d '{
       "mode": "topic-focused",
       "document_id": "...",
       "subject": "Mathematics",
       "count": 10
     }'
   ```

5. **Test Admin Analytics**
   ```bash
   # Get student performance (as admin)
   curl -H "Authorization: Bearer $ADMIN_TOKEN" \
     http://localhost:8000/api/admin/students/{student_id}/performance
   ```

## Troubleshooting

### Issue: "No migration context found"
**Solution**: Make sure you're running from `backend/` directory and `alembic.ini` is present.

### Issue: "Foreign key constraint failed"
**Solution**: Migration likely trying to add foreign key to non-existent table. Check:
- Document table exists
- User table has required columns
- Roll back and re-check migration file

### Issue: "Duplicate key value violates unique constraint"
**Solution**: Existing data conflicts with new constraints:
- Check if `(document_id, shared_with_user_id)` pairs are unique
- May need data cleanup before migration

### Issue: "Column 'education_level' already exists"
**Solution**: Migration already applied. Verify with:
```bash
cd backend
uv run alembic current  # Should show the migration as applied
```

## Performance Considerations

After migration:

1. **New Indexes**: `is_personal`, `is_shared` will improve document filtering
2. **Document Visibility**: Queries now filter by level - ensure indexes are used
3. **Progress Queries**: Admin endpoint computes metrics on-demand (consider caching if slow)

### Monitor Query Performance
```bash
# In PostgreSQL
EXPLAIN ANALYZE SELECT * FROM documents WHERE is_personal = false AND level = 'P6';

# Check index usage
SELECT * FROM pg_stat_user_indexes WHERE relname = 'documents';
```

## Environment Variables

No new environment variables needed. Ensure existing ones are set:

```bash
# backend/.env (or set in environment)
DATABASE_URL=postgresql://exam_prep:exam_prep_dev@localhost:5432/exam_prep
SQLALCHEMY_ECHO=false
WEAK_TOPIC_THRESHOLD=0.60
```

## Documentation Updates

Update these docs for your team:

- [ ] Frontend developers: Add `education_level` to registration form
- [ ] Frontend developers: Update quiz generation to require `document_id`
- [ ] QA: Test level-based document visibility
- [ ] QA: Test document sharing between students
- [ ] Admins: Document new admin analytics endpoints
- [ ] Students: Show new "Share Document" feature in UI

## Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| Pre-deployment | 30 min | Backup DB, review migration |
| Migration | 5-10 min | Run `alembic upgrade head` |
| Testing | 30 min | Verify all components working |
| Deployment | Continuous | Monitor logs, handle issues |
| Validation | 1 hour | Full feature testing |
| Post-deployment | Ongoing | Monitor performance, user feedback |

## Contacts & Support

- Database issues: DBA on call
- Application errors: Backend lead
- User questions: Support team
- Rollback decision: Product manager

---

**Ready to deploy!** 🚀

Follow the steps above and monitor logs closely during deployment.
