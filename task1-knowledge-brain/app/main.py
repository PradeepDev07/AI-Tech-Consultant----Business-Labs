import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import articles, escalation, health, ingestion, providers, questions
from app.config import get_settings
from app.core.exceptions import (
    ArticleNotFoundError,
    AuthenticationError,
    EscalationNotFoundError,
    KnowledgeBrainError,
)
from app.core.logging import logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and graceful shutdown tasks."""
    active_settings = get_settings()
    worker = None
    if active_settings.scheduled_ingestion_enabled:
        from app.dependencies import get_database, get_vector_store_instance
        from ingestion.scheduler import IngestionPipeline, PeriodicIngestionWorker

        pipeline = IngestionPipeline(
            db=get_database(),
            vector_store=get_vector_store_instance(),
            sitemap_url=active_settings.sitemap_url,
            concurrency=active_settings.crawler_concurrency,
            request_delay_seconds=active_settings.crawler_request_delay_seconds,
        )
        worker = PeriodicIngestionWorker(
            pipeline=pipeline,
            interval_hours=active_settings.scheduled_ingestion_interval_hours,
        )
        worker._task = asyncio.create_task(worker.start())
        logger.info("Scheduled ingestion worker started in background.")

    yield

    if worker:
        await worker.stop()
        logger.info("Scheduled ingestion worker terminated.")


app = FastAPI(
    title="Knowledge Brain API",
    description="Knowledge Brain RAG system for Brilliant Directories Solution Center",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(ArticleNotFoundError)
async def article_not_found_handler(request: Request, exc: ArticleNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "Not Found", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(EscalationNotFoundError)
async def escalation_not_found_handler(request: Request, exc: EscalationNotFoundError):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "Not Found", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"error": "Unauthorized", "message": exc.message},
    )


@app.exception_handler(KnowledgeBrainError)
async def general_domain_error_handler(request: Request, exc: KnowledgeBrainError):
    logger.error(f"Domain error occurred: {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "KnowledgeBrainError", "message": exc.message, "details": exc.details},
    )


from pathlib import Path
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Include Routers
app.include_router(health.router)
app.include_router(articles.router)
app.include_router(questions.router)
app.include_router(ingestion.router)
app.include_router(escalation.router)
app.include_router(providers.router)

# Static Dashboard
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/dashboard", response_class=FileResponse)
async def dashboard():
    """Serve the interactive unified capstone dashboard."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse(status_code=404, content={"error": "Dashboard static file not found"})


@app.get("/")
async def root(request: Request):
    """Root endpoint welcoming clients, serving dashboard to browsers, JSON to API clients."""
    accept = request.headers.get("accept", "")
    index_file = static_dir / "index.html"
    if "text/html" in accept and index_file.exists():
        return FileResponse(str(index_file))
    return {
        "service": "Knowledge Brain API",
        "documentation": "/docs",
        "dashboard": "/dashboard",
        "health": "/health",
        "version": "0.1.0",
    }
