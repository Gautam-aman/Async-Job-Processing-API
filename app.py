"""Inventory and async job processing API."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./jobs.db",
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    text: Mapped[str] = mapped_column(String(10000))
    result: Mapped[str | None] = mapped_column(String(10000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JobCreate(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    text: str
    result: str | None
    status: str
    created_at: datetime


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    price_cents: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer)


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price_cents: int = Field(gt=0)
    stock: int = Field(ge=0)


class ProductResponse(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


ProductRead = ProductResponse

Base.metadata.create_all(engine)


def get_db():
    with SessionLocal() as db:
        yield db


get_session = get_db
Db = Annotated[Session, Depends(get_db)]


def process_job(job_id: str) -> None:
    with SessionLocal.begin() as session:
        job = session.get(Job, job_id)
        if job is None or job.status == "completed":
            return
        job.status = "running"

    try:
        with SessionLocal.begin() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.result = job.text.upper()
                job.status = "completed"
    except Exception:
        with SessionLocal.begin() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.status = "failed"
        raise


async def worker(queue: asyncio.Queue[str]) -> None:
    while True:
        job_id = await queue.get()
        try:
            await asyncio.to_thread(process_job, job_id)
        except Exception:
            # The job is marked failed; keep the worker alive for later jobs.
            pass
        finally:
            queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    app.state.queue = asyncio.Queue()
    with SessionLocal() as session:
        pending = session.scalars(
            select(Job.id).where(Job.status.in_(["queued", "running"]))
        ).all()
    for job_id in pending:
        app.state.queue.put_nowait(job_id)
    task = asyncio.create_task(worker(app.state.queue))
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Inventory API", lifespan=lifespan)
app.state.queue = asyncio.Queue()


# --- Product Endpoints ---


@app.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(data: ProductCreate, db: Db):
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.get(
    "/products",
    response_model=list[ProductResponse],
)
def list_products(db: Db):
    return db.scalars(select(Product).order_by(Product.id)).all()


@app.get(
    "/products/{product_id}",
    response_model=ProductResponse,
)
def get_product(product_id: int, db: Db):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


@app.put(
    "/products/{product_id}",
    response_model=ProductResponse,
)
def update_product(
    product_id: int,
    data: ProductCreate,
    db: Db,
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    for field, value in data.model_dump().items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return product


@app.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_product(product_id: int, db: Db):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Job Endpoints ---


@app.post("/jobs", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
async def create_job(data: JobCreate, db: Db):
    job = Job(
        id=str(uuid4()),
        text=data.text,
        status="queued",
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    app.state.queue.put_nowait(job.id)
    return job


@app.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Db):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return job


@app.get("/jobs", response_model=list[JobRead])
def list_jobs(db: Db):
    return db.scalars(select(Job).order_by(Job.created_at.desc())).all()


@app.get("/jobs/{job_id}/events")
async def job_events(job_id: str, db: Db):
    if db.get(Job, job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    async def events():
        last_status = None
        while True:
            with SessionLocal() as current_session:
                job = current_session.get(Job, job_id)
                if job is None:
                    return
                status = job.status
                payload = JobRead.model_validate(job).model_dump(mode="json")
            if status != last_status:
                yield f"event: status\ndata: {json.dumps(payload)}\n\n"
                last_status = status
            if status in {"completed", "failed"}:
                return
            await asyncio.sleep(0.2)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
