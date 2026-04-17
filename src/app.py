"""High School Management System API with role-aware authentication."""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 2
VALID_ROLES = {"student", "club_admin", "super_admin"}


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: str | None = None


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _make_password_record(password: str) -> str:
    salt = os.urandom(8).hex()
    digest = _hash_password(password, salt)
    return f"{salt}${digest}"


def _verify_password(password: str, stored_record: str) -> bool:
    try:
        salt, expected_digest = stored_record.split("$", 1)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Invalid password record") from exc

    actual_digest = _hash_password(password, salt)
    return hmac.compare_digest(actual_digest, expected_digest)


def _create_token(email: str, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS)
    payload = {
        "sub": email,
        "role": role,
        "exp": expires_at,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# In-memory users for this exercise. Keys are normalized lower-case emails.
users = {
    "student@mergington.edu": {
        "email": "student@mergington.edu",
        "password": _make_password_record("student123"),
        "role": "student",
    },
    "clubadmin@mergington.edu": {
        "email": "clubadmin@mergington.edu",
        "password": _make_password_record("clubadmin123"),
        "role": "club_admin",
    },
    "superadmin@mergington.edu": {
        "email": "superadmin@mergington.edu",
        "password": _make_password_record("superadmin123"),
        "role": "super_admin",
    },
}

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    email = str(payload.get("sub", "")).lower().strip()
    role = str(payload.get("role", "")).strip()
    user = users.get(email)

    if not user or user["role"] != role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    return {"email": user["email"], "role": user["role"]}


def require_roles(*roles: str):
    def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this resource",
            )
        return current_user

    return checker


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/register")
def register(payload: RegisterRequest):
    email = payload.email.lower().strip()
    role = payload.role.strip().lower()

    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    if email in users:
        raise HTTPException(status_code=400, detail="Email is already registered")

    users[email] = {
        "email": email,
        "password": _make_password_record(payload.password),
        "role": role,
    }

    return {
        "message": "Registration successful",
        "user": {"email": email, "role": role},
    }


@app.post("/login")
def login(payload: LoginRequest):
    email = payload.email.lower().strip()
    user = users.get(email)

    if not user or not _verify_password(payload.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if payload.role and payload.role.strip().lower() != user["role"]:
        raise HTTPException(status_code=401, detail="Role does not match this account")

    token = _create_token(user["email"], user["role"])

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"email": user["email"], "role": user["role"]},
    }


@app.post("/logout")
def logout(_: dict = Depends(get_current_user)):
    # JWT is stateless; client-side token removal completes logout.
    return {"message": "Logout successful"}


@app.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user


@app.get("/admin/health")
def admin_health(_: dict = Depends(require_roles("club_admin", "super_admin"))):
    return {"message": "Admin access granted"}


@app.get("/super/health")
def super_health(_: dict = Depends(require_roles("super_admin"))):
    return {"message": "Super admin access granted"}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, current_user: dict = Depends(get_current_user)):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    email = current_user["email"]

    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(
    activity_name: str,
    email: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    target_email = (email or current_user["email"]).lower().strip()

    if current_user["role"] == "student" and target_email != current_user["email"]:
        raise HTTPException(
            status_code=403,
            detail="Students can only unregister themselves",
        )

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if target_email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(target_email)
    return {"message": f"Unregistered {target_email} from {activity_name}"}
