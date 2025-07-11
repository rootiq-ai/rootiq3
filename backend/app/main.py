from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from loguru import logger

from app.api import alerts, groups, rca
from app.database.connection import init_db
from app.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Alert Monitoring MVP...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down Alert Monitoring MVP...")


app = FastAPI(
    title="Alert Monitoring MVP",
    description="Alert monitoring system with RCA generation using RAG and LLM",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(groups.router, prefix="/api/groups", tags=["groups"])
app.include_router(rca.router, prefix="/api/rca", tags=["rca"])


@app.get("/")
async def root():
    return {"message": "Alert Monitoring MVP API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )
