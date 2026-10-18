"""FastAPI application entry point for Task 3 Meeting to Scope Agent."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.routes import health, proposals, providers, scope, transcripts

settings = get_settings()

app = FastAPI(
    title="AI Tech Consultant — Meeting to Scope Agent",
    description="Converts discovery transcripts into structured requirements, grounded feasibility findings, effort estimates, scope documents, and change diffs.",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(transcripts.router)
app.include_router(scope.router)
app.include_router(proposals.router)
app.include_router(providers.router)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Translate domain value errors into clean 400 Bad Request responses."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
