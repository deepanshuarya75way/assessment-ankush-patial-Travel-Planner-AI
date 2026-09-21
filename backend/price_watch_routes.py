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



class AlertSettingsUpdateSchema(BaseModel):
    """Payload to update notification channel preferences from the frontend profile."""
    email_enabled: Optional[bool] = None
    web_push_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    alert_on_all_drops: Optional[bool] = None
    digest_mode: Optional[bool] = None


class ScraperPriceUpdatePayload(BaseModel):
    """Payload received from web scrapers submitting real-time pricing tracking snapshots."""
    watch_id: int
    scraped_price: Decimal = Field(..., max_digits=10, decimal_places=2)


@router.get("/user/{user_id}/settings", status_code=status.HTTP_200_OK)
def get_user_alert_settings(user_id: int, db: Session = Depends(get_db)):
    """
    Fetch the custom notification channel choices configured by the traveler.
    """
    settings = db.query(AlertSettingsORM).filter(AlertSettingsORM.user_id == user_id).first()
    
    # If no configuration rule is found in storage memory yet, initialize defaults
    if not settings:
        settings = AlertSettingsORM(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
        
    return settings


@router.patch("/user/{user_id}/settings", status_code=status.HTTP_200_OK)
def update_user_alert_settings(user_id: int, payload: AlertSettingsUpdateSchema, db: Session = Depends(get_db)):
    """
    Update notification channels (Email, WhatsApp, Push) from the user profile settings page.
    """
    settings = db.query(AlertSettingsORM).filter(AlertSettingsORM.user_id == user_id).first()
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings registry block not found.")

    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    return settings


@router.post("/process-update", status_code=status.HTTP_200_OK)
async def ingest_scraper_price(
    payload: ScraperPriceUpdatePayload, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    """
    Endpoint for web scrapers or background workers to submit fresh flight/hotel prices.
    Evaluates drop logic and fires external notification tasks asynchronously.
    """
    # 1. Run core price evaluation business logic rules
    alert_record = PriceWatchService.process_price_update(
        db=db, 
        watch_id=payload.watch_id, 
        new_scraped_price=payload.scraped_price
    )
    
    # 2. If an alert was generated, hand off delivery to background workers
    # This prevents the web scraper execution thread from hanging during API calls to SendGrid or Twilio
    if alert_record:
        background_tasks.add_task(AlertService.dispatch_alert, db, alert_record)
        return {"status": "success", "detail": "Price evaluated. Alert triggered and dispatched to background pipeline."}

    return {"status": "success", "detail": "Price updated successfully. No alert conditions were met."}

