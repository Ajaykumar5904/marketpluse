from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import Role, create_access_token, create_refresh_token, decode_token, hash_password, has_role, verify_password
from app.models import ListingSnapshot, PriceChange, Project, ScrapingRun, Source, User, Workspace
from app.schemas import ChangeOut, LoginIn, ListingOut, ProjectIn, ProjectOut, RefreshIn, RegisterIn, RunOut, SourceIn, SourceOut, TokenOut
from app.services.pipeline import create_run, execute_run

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_token(credentials.credentials, "access")
        user_id = int(claims["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or does not exist")
    return user


def require_role(user: User, role: Role) -> None:
    try:
        allowed = has_role(user.role, role)
    except (ValueError, KeyError):
        allowed = False
    if not allowed:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.post("/auth/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    # Open registration is limited to initial bootstrap to avoid granting admin to arbitrary users.
    if db.scalar(select(User.id).limit(1)) is not None:
        raise HTTPException(status_code=403, detail="Registration is closed; ask a workspace administrator")
    if db.scalar(select(User.id).where(User.email == data.email.lower())) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    workspace = Workspace(name=data.workspace_name)
    db.add(workspace)
    db.flush()
    user = User(email=data.email.lower(), password_hash=hash_password(data.password), role="admin", workspace_id=workspace.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id, user.role), refresh_token=create_refresh_token(user.id))


@router.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenOut(access_token=create_access_token(user.id, user.role), refresh_token=create_refresh_token(user.id))


@router.post("/auth/refresh", response_model=TokenOut)
def refresh(data: RefreshIn, db: Session = Depends(get_db)):
    try:
        claims = decode_token(data.refresh_token, "refresh")
        user_id = int(claims["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User is inactive or does not exist")
    return TokenOut(access_token=create_access_token(user.id, user.role), refresh_token=create_refresh_token(user.id))


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "role": user.role, "workspace_id": user.workspace_id}


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(Project).where(Project.workspace_id == user.workspace_id).order_by(Project.id)))


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_role(user, Role.ANALYST)
    project = Project(workspace_id=user.workspace_id, **data.model_dump(mode="json"))
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == user.workspace_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/projects/{project_id}/sources", response_model=SourceOut, status_code=201)
def create_source(project_id: int, data: SourceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_role(user, Role.ANALYST)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == user.workspace_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if data.scraper_type not in {"static", "javascript", "api"}:
        raise HTTPException(status_code=422, detail="scraper_type must be static, javascript, or api")
    source = Source(project_id=project.id, **data.model_dump(mode="json"))
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.get("/projects/{project_id}/sources", response_model=list[SourceOut])
def list_sources(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == user.workspace_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return list(db.scalars(select(Source).where(Source.project_id == project.id).order_by(Source.id)))


@router.post("/sources/{source_id}/runs", response_model=RunOut, status_code=202)
def start_source_run(source_id: int, background_tasks: BackgroundTasks,
                     user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_role(user, Role.ANALYST)
    source = db.scalar(select(Source).join(Project).where(
        Source.id == source_id, Project.workspace_id == user.workspace_id, Source.enabled.is_(True)
    ))
    if source is None:
        raise HTTPException(status_code=404, detail="Enabled source not found")
    run = create_run(db, source)
    background_tasks.add_task(execute_run, run.id)
    return run


@router.get("/sources/{source_id}/runs", response_model=list[RunOut])
def list_source_runs(source_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    source = db.scalar(select(Source).join(Project).where(
        Source.id == source_id, Project.workspace_id == user.workspace_id
    ))
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return list(db.scalars(select(ScrapingRun).where(ScrapingRun.source_id == source.id)
                           .order_by(ScrapingRun.id.desc()).limit(50)))


@router.get("/projects/{project_id}/changes", response_model=list[ChangeOut])
def list_project_changes(project_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == user.workspace_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    stmt = (select(PriceChange).join(ListingSnapshot).join(Source)
            .where(Source.project_id == project.id).order_by(PriceChange.detected_at.desc()).limit(500))
    return list(db.scalars(stmt))


@router.get("/projects/{project_id}/listings", response_model=list[ListingOut])
def list_listings(project_id: int, include_removed: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.workspace_id == user.workspace_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    stmt = select(ListingSnapshot).join(Source).where(Source.project_id == project.id)
    if not include_removed:
        stmt = stmt.where(ListingSnapshot.removed_at.is_(None))
    return list(db.scalars(stmt.order_by(ListingSnapshot.last_seen_at.desc()).limit(500)))
