"""User registration, login, and profile routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User, EducationLevelEnum, AccountTypeEnum
from app.db.session import get_db
from app.api.deps import get_current_user
from app.api.subjects import auto_enroll_user_in_level
from app.schemas.user import UserCreate, UserLogin, UserRead, UserUpdate, Token, AuthResponse

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, db: Session = Depends(get_db)):
    """Create a new student or admin account."""
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        account_type=AccountTypeEnum(body.account_type.value),
        education_level=(
            EducationLevelEnum(body.education_level.value)
            if body.education_level
            else None
        ),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Auto-enroll practice users (e.g. DRIVING) into all subjects for their level
    if (
        user.account_type == AccountTypeEnum.PRACTICE
        and user.education_level is not None
    ):
        auto_enroll_user_in_level(db, user.id, user.education_level)

    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return AuthResponse(access_token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    """Authenticate and return a JWT access token + user profile."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )

    token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return AuthResponse(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user


@router.patch("/me", response_model=UserRead)
def update_profile(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the authenticated user's profile (full_name, account_type, education_level)."""
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.account_type is not None:
        current_user.account_type = AccountTypeEnum(body.account_type.value)
    if body.education_level is not None:
        current_user.education_level = EducationLevelEnum(body.education_level.value)
    db.commit()
    db.refresh(current_user)
    return current_user
