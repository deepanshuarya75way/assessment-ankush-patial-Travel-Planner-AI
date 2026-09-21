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
