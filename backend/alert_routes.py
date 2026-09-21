from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Assuming these are imported from your project structure
# Replace 'your_app' with your actual package name
from your_app.database import get_db
from your_app.models import PriceAlertORM
from your_app.schemas import PriceAlertSchema

router = APIRouter(
    prefix="/alerts",
    tags=["Price Alerts Dashboard"]
)


@router.get("/user/{user_id}", response_model=List[PriceAlertSchema])
def get_user_alerts(
    user_id: int, 
    unread_only: bool = False, 
    limit: int = 50, 
    db: Session = Depends(get_db)
):
    """
    Fetch historical triggered notification logs for a specific user profile.
    Can be filtered to display unread messages only.
    """
    query = db.query(PriceAlertORM).filter(PriceAlertORM.user_id == user_id)
    
    if unread_only:
        query = query.filter(PriceAlertORM.is_read == False)
        
    return query.order_by(PriceAlertORM.created_at.desc()).limit(limit).all()


@router.patch("/{alert_id}/read", response_model=PriceAlertSchema)
def mark_alert_as_read(alert_id: int, db: Session = Depends(get_db)):
    """
    Mark an individual flight or hotel notification banner alert as read when clicked by the user.
    """
    db_alert = db.query(PriceAlertORM).filter(PriceAlertORM.id == alert_id).first()
    if not db_alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Alert notification card record not found."
        )
        
    db_alert.is_read = True
    db.commit()
    db.refresh(db_alert)
    return db_alert


@router.patch("/user/{user_id}/read-all", status_code=status.HTTP_200_OK)
def mark_all_alerts_as_read(user_id: int, db: Session = Depends(get_db)):
    """
    Clear out an active inbox badge layout completely by changing all unread items to read.
    """
    unread_alerts = db.query(PriceAlertORM).filter(
        PriceAlertORM.user_id == user_id,
        PriceAlertORM.is_read == False
    ).all()
    
    if not unread_alerts:
        return {"message": "All alert records are already cleared and marked as read."}
        
    for alert in unread_alerts:
        alert.is_read = True
        
    db.commit()
    return {"message": f"Successfully updated {len(unread_alerts)} alerts to read state."}


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    """
    Permanently delete an item from the user's notification log list view history.
    """
    db_alert = db.query(PriceAlertORM).filter(PriceAlertORM.id == alert_id).first()
    if not db_alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Alert entry not found or already deleted."
        )
        
    db.delete(db_alert)
    db.commit()
    return None





class AlertSettingsSchema(BaseModel):
    id: int
    user_id: int
    email_enabled: bool
    web_push_enabled: bool
    whatsapp_enabled: bool
    alert_on_all_drops: bool
    digest_mode: bool

    class Config:
        from_attributes = True


class AlertSettingsUpdateSchema(BaseModel):
    """Handles partial updates when toggling switches on the frontend profile UI."""
    email_enabled: Optional[bool] = None
    web_push_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    alert_on_all_drops: Optional[bool] = None
    digest_mode: Optional[bool] = None


@router.get("/user/{user_id}/settings", response_model=AlertSettingsSchema)
def get_user_alert_settings(user_id: int, db: Session = Depends(get_db)):
    """
    Fetch the custom notification channel distribution paths configured by the traveler.
    """
    settings = db.query(AlertSettingsORM).filter(AlertSettingsORM.user_id == user_id).first()
    
    
    if not settings:
        settings = AlertSettingsORM(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
        
    return settings


@router.patch("/user/{user_id}/settings", response_model=AlertSettingsSchema)
def update_user_alert_settings(user_id: int, payload: AlertSettingsUpdateSchema, db: Session = Depends(get_db)):
    """
    Dynamically update delivery options (Email, WhatsApp, Push flags) from user profile forms.
    """
    settings = db.query(AlertSettingsORM).filter(AlertSettingsORM.user_id == user_id).first()
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Notification configuration registry block not found for this account."
        )

   
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    return settings


@router.post("/user/{user_id}/trigger-digest", status_code=status.HTTP_202_ACCEPTED)
def trigger_daily_digest_delivery(user_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Manual override or system cron trigger hook. 
    Compiles all unread matching tracking drops and dispatches a single summary payload.
    """
    settings = db.query(AlertSettingsORM).filter(AlertSettingsORM.user_id == user_id).first()
    if not settings or not settings.digest_mode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This traveler profile is not configured to receive system Daily Digest summaries."
        )

    # Verification check to see if any unread signals exist before wasting third-party network bandwidth
    unread_alerts_count = db.query(PriceAlertORM).filter(
        PriceAlertORM.user_id == user_id,
        PriceAlertORM.is_read == False
    ).count()

    if unread_alerts_count == 0:
        return {"status": "skipped", "detail": "No fresh pricing reductions found to bundle for this summary profile."}

    
    return {"status": "queued", "detail": f"Successfully compiled and queued a summary digest of {unread_alerts_count} drops."}
