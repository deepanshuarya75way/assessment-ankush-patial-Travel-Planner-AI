from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

# Assuming these are imported from your project structure
# Replace 'your_app' with your actual package name
from your_app.database import get_db
from your_app.models import PriceWatchORM, PriceAlertORM
from your_app.schemas import PriceWatchSchema, PriceAlertSchema

router = APIRouter(
    prefix="/price-watches",
    tags=["Price Watch & Alerts"]
)

@router.post("/", response_model=PriceWatchSchema, status_code=status.HTTP_201_CREATED)
def create_price_watch(payload: PriceWatchSchema, db: Session = Depends(get_db)):
    """
    Create a new trip price tracking subscription.
    """
    # Prevent creating duplicate active watches for the exact same route and date
    existing_watch = db.query(PriceWatchORM).filter(
        PriceWatchORM.user_id == payload.user_id,
        PriceWatchORM.origin == payload.origin,
        PriceWatchORM.destination == payload.destination,
        PriceWatchORM.travel_date == payload.travel_date,
        PriceWatchORM.is_active == True
    ).first()
    
    if existing_watch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already actively tracking this exact trip route and date."
        )

    # Convert Pydantic payload to SQLAlchemy ORM object
    db_watch = PriceWatchORM(
        user_id=payload.user_id,
        origin=payload.origin,
        destination=payload.destination,
        travel_date=payload.travel_date,
        initial_price=float(payload.initial_price),
        current_price=float(payload.current_price),
        target_price=float(payload.target_price) if payload.target_price else None,
        trigger_percent_drop=payload.trigger_percent_drop,
        currency=payload.currency,
        is_active=payload.is_active
    )
    
    db.add(db_watch)
    db.commit()
    db.refresh(db_watch)
    return db_watch


@router.get("/user/{user_id}", response_model=List[PriceWatchSchema])
def get_user_price_watches(user_id: int, active_only: bool = True, db: Session = Depends(get_db)):
    """
    Retrieve all configuration trackers configured by a specific user.
    """
    query = db.query(PriceWatchORM).filter(PriceWatchORM.user_id == user_id)
    
    if active_only:
        query = query.filter(PriceWatchORM.is_active == True)
        
    return query.all()


@router.patch("/{watch_id}/deactivate", response_model=PriceWatchSchema)
def deactivate_price_watch(watch_id: int, db: Session = Depends(get_db)):
    """
    Turn off notifications and tracking for a specific trip config rule.
    """
    db_watch = db.query(PriceWatchORM).filter(PriceWatchORM.id == watch_id).first()
    if not db_watch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price watch configuration not found.")
        
    db_watch.is_active = False
    db.commit()
    db.refresh(db_watch)
    return db_watch


@router.get("/user/{user_id}/alerts", response_model=List[PriceAlertSchema])
def get_user_price_alerts(user_id: int, unread_only: bool = False, db: Session = Depends(get_db)):
    """
    Fetch historical triggered notification alerts for a user.
    """
    query = db.query(PriceAlertORM).filter(PriceAlertORM.user_id == user_id)
    
    if unread_only:
        query = query.filter(PriceAlertORM.is_read == False)
        
    return query.order_by(PriceAlertORM.created_at.desc()).all()


@router.patch("/alerts/{alert_id}/read", response_model=PriceAlertSchema)
def mark_alert_as_read(alert_id: int, db: Session = Depends(get_db)):
    """
    Mark an active notification banner alert as read when clicked by user.
    """
    db_alert = db.query(PriceAlertORM).filter(PriceAlertORM.id == alert_id).first()
    if not db_alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert record not found.")
        
    db_alert.is_read = True
    db.commit()
    db.refresh(db_alert)
    return db_alert
