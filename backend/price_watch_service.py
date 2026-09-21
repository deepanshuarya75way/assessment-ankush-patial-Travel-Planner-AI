from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

# Assuming these are imported from your project architecture
from your_app.models import PriceWatchORM, PriceAlertORM


class PriceWatchService:

    @staticmethod
    def process_price_update(db: Session, watch_id: int, new_scraped_price: Decimal) -> Optional[PriceAlertORM]:
        """
        Processes a fresh, web-scraped price update for an active trip.
        Updates the database status and fires an alert if evaluation criteria are met.
        """
        # 1. Fetch the active tracking profile
        db_watch = db.query(PriceWatchORM).filter(
            PriceWatchORM.id == watch_id,
            PriceWatchORM.is_active == True
        ).first()

        if not db_watch:
            return None

        # Cache variables for math checks
        new_price_float = float(new_scraped_price)
        old_price_float = db_watch.current_price
        initial_price_float = db_watch.initial_price
        
        # 2. Always keep our current price status record fresh
        db_watch.current_price = new_price_float
        db_watch.updated_at = datetime.utcnow()
        
        # 3. Core matching criteria evaluation logic
        should_trigger = False
        alert_reason = ""

        # Condition A: Check if it fell below an absolute target threshold limit
        if db_watch.target_price is not None:
            if new_price_float <= db_watch.target_price and new_price_float < old_price_float:
                should_trigger = True
                alert_reason = f"Price dropped to {db_watch.currency} {new_price_float}, hitting your target price of {db_watch.currency} {db_watch.target_price}!"

        # Condition B: Check percentage drops compared to baseline creation price
        if db_watch.trigger_percent_drop is not None and not should_trigger:
            price_delta = initial_price_float - new_price_float
            if price_delta > 0:
                actual_drop_percent = (price_delta / initial_price_float) * 100
                if actual_drop_percent >= db_watch.trigger_percent_drop and new_price_float < old_price_float:
                    should_trigger = True
                    alert_reason = f"Price dropped by {int(actual_drop_percent)}%! It is now {db_watch.currency} {new_price_float} (Initial baseline: {db_watch.currency} {initial_price_float})."

        # 4. Action generation if threshold criteria are met
        alert_record = None
        if should_trigger:
            alert_record = PriceAlertORM(
                user_id=db_watch.user_id,
                watch_id=db_watch.id,
                title=f"Price Drop Alert: {db_watch.origin} ✈️ {db_watch.destination}",
                message=alert_reason,
                price=new_price_float,
                is_read=False,
                created_at=datetime.utcnow()
            )
            db.add(alert_record)

        # Commit all transaction updates atomically
        db.commit()
        
        if alert_record:
            db.refresh(alert_record)
            
        return alert_record

    @staticmethod
    def batch_evaluate_scraped_data(db: Session, origin: str, destination: str, travel_date: datetime, scraped_price: Decimal):
        """
        Alternative helper logic: If your scraper yields raw route results without knowing watch IDs, 
        this finds ALL matching active user profiles for that specific route and cross-evaluates them at once.
        """
        matching_watches = db.query(PriceWatchORM).filter(
            PriceWatchORM.origin == origin,
            PriceWatchORM.destination == destination,
            PriceWatchORM.travel_date == travel_date,
            PriceWatchORM.is_active == True
        ).all()

        triggered_alerts = []
        for watch in matching_watches:
            alert = PriceWatchService.process_price_update(db, watch.id, scraped_price)
            if alert:
                triggered_alerts.append(alert)
                
        return triggered_alerts
