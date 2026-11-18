import os

from typing import Annotated
from fastapi import (
    FastAPI, Depends, HTTPException, Response
)

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://app:app@localhost:5432/products"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(100)
    )

    price_cents: Mapped[int]
    stock: Mapped[int]

# Request DTO
class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price_cents: int = Field(gt=0)
    stock: int = Field(ge=0)

class ProductResponse(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


def get_db():
    with SessionLocal() as db:
        yield db

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    price_cents: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer)


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    price_cents: int = Field(ge=0)
    stock: int = Field(ge=0)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price_cents: int
    stock: int


Base.metadata.create_all(engine)


Db = Annotated[Session, Depends(get_db)]

app = FastAPI(title="Inventory API")

@app.post(
    "/products",
    response_model=ProductResponse,
    status_code=201
)
def create_product(data: ProductCreate, db: Db):
    product = Product(**data.model_dump())

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


@app.get(
    "/products",
    response_model=list[ProductResponse]
)
def list_products(db: Db):
    return db.scalars(
        select(Product).order_by(Product.id)
    ).all()


@app.get(
    "/products/{product_id}",
    response_model=ProductResponse
)
def get_product(product_id: int, db: Db):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )
app.state.queue = asyncio.Queue()

    return product


@app.put(
    "/products/{product_id}",
    response_model=ProductResponse
)
def update_product(
    product_id: int,
    data: ProductCreate,
    db: Db
):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    for field, value in data.model_dump().items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)

    return product


@app.delete(
    "/products/{product_id}",
    status_code=204
)
def delete_product(product_id: int, db: Db):
    product = db.get(Product, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )


@app.post("/products", response_model=ProductRead, status_code=201)
def create_product(data: ProductCreate, session: Session = Depends(get_session)):
    product = Product(name=data.name, price_cents=data.price_cents, stock=data.stock)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@app.get("/products", response_model=list[ProductRead])
def list_products(session: Session = Depends(get_session)):
    return session.scalars(select(Product)).all()


@app.get("/products/{product_id}", response_model=ProductRead)
def get_product(product_id: int, session: Session = Depends(get_session)):
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

    db.delete(product)
    db.commit()

    return Response(status_code=204)