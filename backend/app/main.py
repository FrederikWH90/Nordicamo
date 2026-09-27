"""FastAPI application main file."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import stats, topics, contact, articles, outlets

# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=settings.API_DESCRIPTION,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS middleware (allow Streamlit to access API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stats.router)
app.include_router(topics.router)
app.include_router(contact.router)
app.include_router(articles.router)
app.include_router(outlets.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "NAMO API - Nordic Alternative Media Observatory",
        "version": settings.API_VERSION,
        "docs": "/api/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
