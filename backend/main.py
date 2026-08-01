"""
Cadence - FastAPI Application Entry Point
AI Chief of Staff built on watsonx Orchestrate
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.graph.database import init_db, get_db
from backend.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Startup
    logger.info("Starting Cadence - AI Chief of Staff")
    try:
        db = init_db()
        logger.info("Neo4j connection established and schema initialized")
    except Exception as e:
        logger.warning(f"Neo4j not available at startup: {e}")
        logger.info("Running in demo mode without persistent graph")

    yield

    # Shutdown
    try:
        db = get_db()
        db.close()
    except Exception:
        pass
    logger.info("Cadence shutdown complete")


app = FastAPI(
    title="Cadence - AI Chief of Staff",
    description=(
        "An AI-powered system that turns meeting decisions into tracked commitments. "
        "Built on IBM watsonx Orchestrate with Neo4j knowledge graph."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")
