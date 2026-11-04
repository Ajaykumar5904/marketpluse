from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    workspace_name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="market_research", max_length=30)
    filters: dict = Field(default_factory=dict)
    frequency_cron: str = "0 6 * * *"
    notify_emails: list[EmailStr] = Field(default_factory=list)


class ProjectOut(ProjectIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workspace_id: int
    status: str
    created_at: datetime


class SourceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    url: HttpUrl
    scraper_type: str = "static"
    selectors: dict = Field(default_factory=dict)
    expected_fields: list[str] = Field(default_factory=list)
    frequency_cron: str | None = None
    store_raw_html: bool = False


class SourceOut(SourceIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    enabled: bool
    last_success_at: datetime | None


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    title: str
    url: str
    brand: str | None
    seller: str | None
    location: str | None
    price: Decimal | None
    currency: str | None
    availability: str
    rating: float | None
    review_count: int | None
    first_seen_at: datetime
    last_seen_at: datetime
    removed_at: datetime | None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    pages_fetched: int
    items_extracted: int
    validation_failures: int
    missing_fields: dict
    error: str | None


class ChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    snapshot_id: int
    run_id: int | None
    event_type: str
    old_value: str | None
    new_value: str | None
    abs_change: Decimal | None
    pct_change: Decimal | None
    detected_at: datetime
