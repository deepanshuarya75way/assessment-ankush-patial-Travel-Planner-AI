import logging
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

# Assuming these are imported from your project architecture
from your_app.models import PriceAlertORM, AlertSettingsORM, PriceWatchORM

logger = logging.getLogger(__name__)

class AlertService:

    @classmethod
    async def dispatch_alert(cls, db: Session, alert_record: PriceAlertORM) -> bool:
        """
        Takes a newly created PriceAlertORM record, checks the user's custom 
        AlertSettings, and routes the notification payload to all active channels.
        """
        if not alert_record:
            return False

        # 1. Fetch user's communication channel configurations
        settings = db.query(AlertSettingsORM).filter(
            AlertSettingsORM.user_id == alert_record.user_id
        ).first()

        # If no custom setting record exists, fallback to default behavior (Email & Web Push)
        email_enabled = settings.email_enabled if settings else True
        web_push_enabled = settings.web_push_enabled if settings else True
        whatsapp_enabled = settings.whatsapp_enabled if settings else False

        # 2. Extract context details for communication formatting
        # Using a join or direct relation reference if loaded
        watch_ctx = db.query(PriceWatchORM).filter(PriceWatchORM.id == alert_record.watch_id).first()
        currency_symbol = watch_ctx.currency if watch_ctx else "INR"

        dispatched_any = False

        # Channel A: Email Delivery Layer
        if email_enabled:
            success = await cls._send_email_notification(
                user_id=alert_record.user_id,
                title=alert_record.title,
                message=alert_record.message,
                current_price=alert_record.price,
                currency=currency_symbol
            )
            if success:
                dispatched_any = True

        # Channel B: Web Push Notification Layer
        if web_push_enabled:
            success = await cls._send_web_push_notification(
                user_id=alert_record.user_id,
                title=alert_record.title,
                message=alert_record.message
            )
            if success:
                dispatched_any = True

        # Channel C: WhatsApp Messaging Layer
        if whatsapp_enabled:
            success = await cls._send_whatsapp_notification(
                user_id=alert_record.user_id,
                message=f"*{alert_record.title}*\n{alert_record.message}"
            )
            if success:
                dispatched_any = True

        return dispatched_any

    @staticmethod
    async def _send_email_notification(user_id: int, title: str, message: str, current_price: float, currency: str) -> bool:
        """
        Integrates with your choice of Email Delivery Provider (e.g., SendGrid, Mailgun, Amazon SES).
        """
        try:
            logger.info(f"Sending Email to User {user_id}: [{title}] - {message}")
            # Real integration pattern example:
            # response = sendgrid_client.send(to=user_email, subject=title, html_content=message)
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch email delivery to User {user_id}: {str(e)}")
            return False

    @staticmethod
    async def _send_web_push_notification(user_id: int, title: str, message: str) -> bool:
        """
        Integrates with Web Push architectures or real-time layout channels (e.g., Firebase Cloud Messaging, OneSignal).
        """
        try:
            logger.info(f"Triggering Web Push stream packet to User {user_id}: {title}")
            # Real integration pattern example:
            # fcm_client.send_to_user_topic(user_id, payload={"title": title, "body": message})
            return True
        except Exception as e:
            logger.error(f"Failed to trigger web push message wrapper context: {str(e)}")
            return False

    @staticmethod
    async def _send_whatsapp_notification(user_id: int, message: str) -> bool:
        """
        Integrates with Instant Messaging Business Platforms (e.g., Twilio WhatsApp API, Infobip).
        """
        try:
            logger.info(f"Dispatching WhatsApp Text API pipeline payload to User {user_id}")
            # Real integration pattern example:
            # twilio_client.messages.create(body=message, from_="whatsapp:+14155238886", to=f"whatsapp:{user_phone}")
            return True
        except Exception as e:
            logger.error(f"WhatsApp sandbox execution transaction pipeline failure: {str(e)}")
            return False
