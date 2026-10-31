from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from typing import List, Optional

raw_dishes = [
    {"dish_code": "F301", "category": "main", "price": 15000, "status": "available"},
    {"dish_code": "f101", "category": "appetizer", "price": 55000, "status": "available"},
    {"dish_code": "F202", "category": "dessert", "price": 45000, "status": "sold_out"},
    {"dish_code": "F102", "category": "appetizer", "price": 65000, "status": "unavailable"},
    {"dish_code": "F302", "category": "main", "price": 180000, "status": "available"},
]

def clean_and_validate_dishes(dishes: list) -> list:
    cleaned_list = []
    for d in dishes:
        code = str(d.get("dish_code", "")).strip().upper()
        if code.startswith('F') and code[1:].isdigit():
            item = {
                "dish_code": code,
                "category": d.get("category"),
                "price": float(d.get("price", 0)),
                "status": d.get("status", "available")
            }
            cleaned_list.append(item)
    return cleaned_list

def search_dishes(dishes: list, max_price: float, target_status: Optional[str] = None) -> list:
    valid_dishes = clean_and_validate_dishes(dishes)
    result = []
    for dish in valid_dishes:
        if dish["price"] <= max_price:
            if target_status is None or dish["status"] == target_status:
                result.append(dish)
    return result

def sort_dishes_by_price_desc(dishes: list) -> list:
    arr = list(dishes)
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j]["price"] < arr[j + 1]["price"]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr



SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost:3306/restaurant_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DishCategoryModel(Base):
    __tablename__ = "dish_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    
    dishes = relationship("DishModel", back_populates="category", cascade="all, delete-orphan")

class DishModel(Base):
    __tablename__ = "dishes"
    
    id = Column(Integer, primary_key=True, index=True)
    dish_code = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(100))
    price = Column(Float, nullable=False)
    status = Column(String(50), default="available")
    dish_category_id = Column(Integer, ForeignKey("dish_categories.id"), nullable=False)

    category = relationship("DishCategoryModel", back_populates="dishes")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class CategoryCreate(BaseModel):
    name: str = Field(..., max_length=50)

class CategoryResponse(CategoryCreate):
    id: int
    class Config:
        from_attributes = True

class DishCreate(BaseModel):
    dish_code: str = Field(..., min_length=4, max_length=10)
    name: str
    price: float = Field(..., gt=0)
    status: Optional[str] = "available"
    dish_category_id: int

    @field_validator('dish_code')
    def validate_code(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not (cleaned.startswith('F') and cleaned[1:].isdigit()):
            raise ValueError("dish_code phải bắt đầu bằng 'F' và theo sau là các chữ số!")
        return cleaned

class DishResponse(DishCreate):
    id: int
    class Config:
        from_attributes = True


app = FastAPI(title="Quản lý Nhà hàng")

@app.post("/dish-categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    existing = db.query(DishCategoryModel).filter(DishCategoryModel.name == category.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tên danh mục đã tồn tại!")
    db_cat = DishCategoryModel(name=category.name)
    db.add(db_cat)
    db.commit()
    db.refresh(db_cat)
    return db_cat

@app.delete("/dish-categories/{category_id}", status_code=status.HTTP_200_OK)
def delete_dish_category(category_id: int, db: Session = Depends(get_db)):
    category = db.query(DishCategoryModel).filter(DishCategoryModel.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy danh mục với ID = {category_id}")
    db.delete(category)
    db.commit()
    return {"message": f"Đã xóa thành công danh mục ID {category_id}"}

@app.post("/dishes", response_model=DishResponse, status_code=status.HTTP_201_CREATED)
def create_dish(dish: DishCreate, db: Session = Depends(get_db)):
    cat = db.query(DishCategoryModel).filter(DishCategoryModel.id == dish.dish_category_id).first()
    if not cat:
        raise HTTPException(status_code=400, detail="dish_category_id không tồn tại trong hệ thống!")
        
    db_dish = DishModel(
        dish_code=dish.dish_code,
        name=dish.name,
        price=dish.price,
        status=dish.status,
        dish_category_id=dish.dish_category_id
    )
    db.add(db_dish)
    db.commit()
    db.refresh(db_dish)
    return db_dish

@app.get("/dishes", response_model=List[DishResponse])
def get_dishes(db: Session = Depends(get_db)):
    return db.query(DishModel).all()