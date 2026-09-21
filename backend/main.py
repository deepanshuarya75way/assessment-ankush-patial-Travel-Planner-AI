import asyncio
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.config import logger

from backend.models import (
    AIResponse,
    BudgetRequest,
    ChatRequest,
    ChatResponse,
    FlightRequest,
    HotelRequest,
    ItineraryRequest,
    TravelScore,
    WeatherAnalysis,
    WeatherRequest,
)

from backend.search_service import (
    search_flights,
    search_hotels,
    format_travel_data,
)

from backend.weather_service import fetch_weather_analysis
from backend.budget_service import analyze_budget

from backend.ai_service import (
    get_ai_recommendation,
    generate_itinerary,
    get_chat_response,
    analyze_weather_with_ai,
    analyze_budget_with_ai,
    generate_travel_score,
)

# ── Database ────────────────────────────────────────────────────────────────
from backend.database.connection import engine, check_db_connection
from backend.database import models as db_models  # noqa: F401 — registers all ORM models

# ── New API routers ─────────────────────────────────────────────────────────
from backend.auth.router import router as auth_router
from backend.api.health import router as health_router
from backend.api.destinations import router as destinations_router
from backend.api.planners import router as planners_router
from backend.api.packages import router as packages_router
from backend.api.trips import router as trips_router
from backend.api.reviews import router as reviews_router
from backend.api.favorites import router as favorites_router
from backend.api.ai_trips import router as ai_trips_router
from backend.api.chat import router as chat_router
from backend.api.blogs import router as blogs_router
from backend.api.site_feedback import router as site_feedback_router
from backend.auth.utils import get_current_user
from backend.database.models import User
from .price_watch_routes import router as price_watch_routes
from .alert_routes import router as alert_router

app = FastAPI(title="Travel Planning API", version="2.0.0")

# ── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register new routers ─────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(destinations_router)
app.include_router(planners_router)
app.include_router(packages_router)
app.include_router(trips_router)
app.include_router(reviews_router)
app.include_router(favorites_router)
app.include_router(ai_trips_router)
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
app.include_router(blogs_router, prefix="/api/blogs", tags=["Blogs"])
app.include_router(site_feedback_router)
app.include_router(price_watch_router)
app.include_router(alert_router)


# ── Startup: create tables if not already present ───────────────────────────
@app.on_event("startup")
async def startup_event():
    try:
        db_models.Base.metadata.create_all(bind=engine)
        if check_db_connection():
            logger.info("✅ MySQL database connected and tables verified.")
        else:
            logger.warning("⚠️  MySQL not reachable — DB features unavailable.")
    except Exception as exc:
        logger.warning("⚠️  DB startup warning (non-fatal): %s", exc)


# ── Health ──────────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Travel Planning API", "version": "2.0.0"}



# ── Flights ────────────────────────────────────────────────────────────
@app.post("/search_flights/", response_model=AIResponse)
async def get_flight_recommendations(flight_request: FlightRequest):
    try:
        flights = await search_flights(flight_request)

        if isinstance(flights, dict) and "error" in flights:
            raise HTTPException(status_code=400, detail=flights["error"])
        if not flights:
            raise HTTPException(status_code=404, detail="No flights found")

        flights_text = format_travel_data("flights", flights)

        # AI recommendation is non-critical
        try:
            recommendation = await get_ai_recommendation("flights", flights_text)
        except Exception as ai_exc:
            logger.error("AI flight recommendation failed (non-fatal): %s", ai_exc)
            recommendation = "AI analysis temporarily unavailable. Flight data is shown below."

        return AIResponse(flights=flights, ai_flight_recommendation=recommendation)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Flight search endpoint error")
        raise HTTPException(status_code=500, detail=f"Flight search error: {exc}") from exc


# ── Hotels ─────────────────────────────────────────────────────────────
@app.post("/search_hotels/", response_model=AIResponse)
async def get_hotel_recommendations(hotel_request: HotelRequest):
    try:
        hotels = await search_hotels(hotel_request)

        if isinstance(hotels, dict) and "error" in hotels:
            raise HTTPException(status_code=400, detail=hotels["error"])
        if not hotels:
            raise HTTPException(status_code=404, detail="No hotels found")

        hotels_text = format_travel_data("hotels", hotels)

        try:
            recommendation = await get_ai_recommendation("hotels", hotels_text)
        except Exception as ai_exc:
            logger.error("AI hotel recommendation failed (non-fatal): %s", ai_exc)
            recommendation = "AI analysis temporarily unavailable. Hotel data is shown below."

        return AIResponse(hotels=hotels, ai_hotel_recommendation=recommendation)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Hotel search endpoint error")
        raise HTTPException(status_code=500, detail=f"Hotel search error: {exc}") from exc


# ── Weather Intelligence ───────────────────────────────────────────────
@app.post("/search_weather/", response_model=WeatherAnalysis)
async def get_weather_intelligence(weather_request: WeatherRequest):
    """
    Fetch real-time weather data for the destination, detect risks,
    and generate AI-powered travel recommendations.
    """
    try:
        # 1. Fetch and process raw weather data
        weather = await fetch_weather_analysis(weather_request)

        # 2. AI narrative analysis (non-critical)
        try:
            ai_text = await analyze_weather_with_ai(
                destination=weather_request.destination,
                weather=weather,
                start_date=weather_request.start_date,
                end_date=weather_request.end_date,
            )
            weather.ai_weather_summary = ai_text
            weather.travel_recommendation = ai_text  # Same text, structured inside
        except Exception as ai_exc:
            logger.error("AI weather analysis failed (non-fatal): %s", ai_exc)
            weather.ai_weather_summary = (
                f"Weather for {weather_request.destination}: {weather.overall_condition}. "
                f"Temperature range: {weather.temperature_range}. "
                f"Risk level: {weather.risk_level}."
            )

        return weather
    except Exception as exc:
        logger.exception("Weather search endpoint error")
        raise HTTPException(status_code=500, detail=f"Weather search error: {exc}") from exc


# ── Budget Analysis ────────────────────────────────────────────────────
@app.post("/analyze_budget/")
async def get_budget_analysis(budget_request: BudgetRequest):
    """
    Analyze trip budget against actual flight/hotel prices.
    Returns structured cost breakdown and AI optimization advice.
    """
    try:
        # 1. Compute budget breakdown
        budget_analysis = analyze_budget(budget_request)

        # 2. AI narrative (non-critical)
        try:
            ai_text = await analyze_budget_with_ai(
                budget_analysis=budget_analysis,
                destination=budget_request.destination,
                trip_nights=budget_request.trip_nights,
            )
            budget_analysis.ai_budget_analysis = ai_text
        except Exception as ai_exc:
            logger.error("AI budget analysis failed (non-fatal): %s", ai_exc)
            budget_analysis.ai_budget_analysis = (
                f"Budget status: {budget_analysis.budget_status}. "
                f"Estimated cost: ₹{budget_analysis.estimated_total_cost:,.0f} "
                f"vs budget: ₹{budget_analysis.user_budget:,.0f}."
            )

        return budget_analysis
    except Exception as exc:
        logger.exception("Budget analysis endpoint error")
        raise HTTPException(status_code=500, detail=f"Budget analysis error: {exc}") from exc


# ── Complete Search (all agents in parallel) ───────────────────────────
@app.post("/complete_search/", response_model=AIResponse)
async def complete_travel_search(
    flight_request: FlightRequest,
    hotel_request: Optional[HotelRequest] = None,
    current_user: User = Depends(get_current_user),
):
    """
    Master search endpoint — runs flights, hotels, weather, and budget
    analysis in parallel and returns a unified response.
    Weather and budget are non-critical: failures return empty values.
    """
    try:
        if hotel_request is None:
            hotel_request = HotelRequest(
                location=flight_request.destination,
                check_in_date=flight_request.outbound_date,
                check_out_date=flight_request.return_date,
            )

        # ── Parallel Phase 1: Flights + Hotels ─────────────────────
        flight_task = asyncio.create_task(_safe_flight_search(flight_request))
        hotel_task  = asyncio.create_task(_safe_hotel_search(hotel_request))
        flights, hotels = await asyncio.gather(flight_task, hotel_task)

        # ── Parallel Phase 2: AI Recs + Weather + Budget ───────────
        flights_text = format_travel_data("flights", flights)
        hotels_text  = format_travel_data("hotels",  hotels)

        # Compute trip nights
        from datetime import datetime as _dt
        try:
            nights = max(
                (_dt.strptime(flight_request.return_date, "%Y-%m-%d") -
                 _dt.strptime(flight_request.outbound_date, "%Y-%m-%d")).days,
                1
            )
        except Exception:
            nights = 3

        weather_req = WeatherRequest(
            destination=flight_request.destination,
            start_date=flight_request.outbound_date,
            end_date=flight_request.return_date,
        )

        ai_flight_task   = asyncio.create_task(_safe_ai_rec("flights", flights_text))
        ai_hotel_task    = asyncio.create_task(_safe_ai_rec("hotels",  hotels_text))
        weather_task     = asyncio.create_task(_safe_weather(weather_req))

        ai_flight_rec, ai_hotel_rec, weather = await asyncio.gather(
            ai_flight_task, ai_hotel_task, weather_task
        )

        # ── Weather AI narrative ────────────────────────────────────
        if weather:
            try:
                ai_wx = await analyze_weather_with_ai(
                    destination=flight_request.destination,
                    weather=weather,
                    start_date=flight_request.outbound_date,
                    end_date=flight_request.return_date,
                )
                weather.ai_weather_summary    = ai_wx
                weather.travel_recommendation = ai_wx
            except Exception as exc:
                logger.warning("AI weather narrative failed (non-fatal): %s", exc)

        # ── Budget Analysis ─────────────────────────────────────────
        budget_analysis = None
        if flight_request.budget and flight_request.budget > 0:
            try:
                budget_req = BudgetRequest(
                    user_budget=flight_request.budget,
                    destination=flight_request.destination,
                    trip_nights=nights,
                    flights=[f.model_dump() for f in flights],
                    hotels=[h.model_dump() for h in hotels],
                )
                budget_analysis = analyze_budget(budget_req)
                try:
                    ai_bd = await analyze_budget_with_ai(
                        budget_analysis=budget_analysis,
                        destination=flight_request.destination,
                        trip_nights=nights,
                    )
                    budget_analysis.ai_budget_analysis = ai_bd
                except Exception as exc:
                    logger.warning("AI budget narrative failed (non-fatal): %s", exc)
            except Exception as exc:
                logger.warning("Budget analysis failed (non-fatal): %s", exc)

        # ── Itinerary ───────────────────────────────────────────────
        itinerary = ""
        if flights and hotels:
            weather_summary = (
                f"Risk: {weather.risk_level}. {weather.overall_condition}. "
                f"Temp range: {weather.temperature_range}."
                if weather else ""
            )
            try:
                itinerary = await generate_itinerary(
                    destination=flight_request.destination,
                    flights_text=flights_text,
                    hotels_text=hotels_text,
                    check_in_date=flight_request.outbound_date,
                    check_out_date=flight_request.return_date,
                    weather_summary=weather_summary,
                    budget=flight_request.budget,
                )
            except Exception as exc:
                logger.warning("Itinerary generation failed (non-fatal): %s", exc)

        # ── Travel Score ────────────────────────────────────────────
        travel_score = None
        try:
            travel_score = await generate_travel_score(
                destination=flight_request.destination,
                flights=flights,
                hotels=hotels,
                weather=weather,
                budget=budget_analysis,
            )
        except Exception as exc:
            logger.warning("Travel score failed (non-fatal): %s", exc)

        # ── Log final response shape for debugging ─────────────────
        logger.info(
            "complete_search response: flights=%d hotels=%d weather=%s budget=%s score=%s",
            len(flights),
            len(hotels),
            f"{weather.risk_level}/{weather.overall_condition}" if weather else "None",
            f"{budget_analysis.budget_status}" if budget_analysis else "None",
            f"{travel_score.total_score}" if travel_score else "None",
        )

        return AIResponse(
            flights=flights,
            hotels=hotels,
            ai_flight_recommendation=ai_flight_rec,
            ai_hotel_recommendation=ai_hotel_rec,
            itinerary=itinerary,
            weather_analysis=weather,
            budget_analysis=budget_analysis,
            travel_score=travel_score,
        )

    except Exception as exc:
        logger.exception("Complete travel search error")
        raise HTTPException(status_code=500, detail=f"Travel search error: {exc}") from exc


# ── Itinerary Generator ────────────────────────────────────────────────
@app.post("/generate_itinerary/", response_model=AIResponse)
async def get_itinerary(itinerary_request: ItineraryRequest):
    try:
        itinerary = await generate_itinerary(
            destination=itinerary_request.destination,
            flights_text=itinerary_request.flights,
            hotels_text=itinerary_request.hotels,
            check_in_date=itinerary_request.check_in_date,
            check_out_date=itinerary_request.check_out_date,
            budget=itinerary_request.budget,
        )
        return AIResponse(itinerary=itinerary)
    except Exception as exc:
        logger.exception("Itinerary generation error")
        raise HTTPException(status_code=500, detail=f"Itinerary generation error: {exc}") from exc


# ── Travel Assistant Chat ──────────────────────────────────────────────
@app.post("/chat/", response_model=ChatResponse)
async def travel_chat(chat_request: ChatRequest):
    """
    Context-aware travel assistant chat endpoint.
    Accepts the current trip context + conversation history and returns
    a Groq-powered, travel-domain-restricted AI response.
    """
    try:
        reply = await get_chat_response(
            message=chat_request.message,
            context=chat_request.context.model_dump(),
            history=[m.model_dump() for m in chat_request.history],
        )
        return ChatResponse(reply=reply)
    except Exception as exc:
        logger.exception("Chat endpoint error")
        raise HTTPException(status_code=500, detail=f"Chat error: {exc}") from exc


# ── Safe Wrappers (for parallel gather) ───────────────────────────────

async def _safe_flight_search(req: FlightRequest):
    try:
        result = await search_flights(req)
        if isinstance(result, dict) and "error" in result:
            logger.error("Flight search returned error: %s", result["error"])
            return []
        return result or []
    except Exception as exc:
        logger.error("Flight search failed: %s", exc)
        return []


async def _safe_hotel_search(req: HotelRequest):
    try:
        result = await search_hotels(req)
        if isinstance(result, dict) and "error" in result:
            logger.error("Hotel search returned error: %s", result["error"])
            return []
        return result or []
    except Exception as exc:
        logger.error("Hotel search failed: %s", exc)
        return []


async def _safe_ai_rec(data_type: str, text: str) -> str:
    try:
        return await get_ai_recommendation(data_type, text)
    except Exception as exc:
        logger.error("AI %s recommendation failed: %s", data_type, exc)
        return f"AI analysis temporarily unavailable for {data_type}."


async def _safe_weather(req: WeatherRequest) -> Optional[WeatherAnalysis]:
    try:
        return await fetch_weather_analysis(req)
    except Exception as exc:
        logger.error("Weather fetch failed (non-fatal): %s", exc)
        return None


# ── Static Frontend ────────────────────────────────────────────────────
import os as _os
app.mount(
    "/",
    StaticFiles(
        directory=_os.path.join(_os.path.dirname(__file__), "..", "frontend"),
        html=True,
    ),
    name="frontend",
)


if __name__ == "__main__":
    logger.info("Starting Travel Planning API v2.0 server")
    uvicorn.run(app, host="0.0.0.0", port=8000)
