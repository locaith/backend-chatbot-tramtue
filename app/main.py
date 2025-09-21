"""
Main FastAPI application
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import structlog
import time

from app.core.config import get_config
from app.core.logging import setup_logging, RequestLogger
from app.api import health, chat, rag, timers, admin, streaming

# Setup logging
setup_logging()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting TramTue ChatBot AI Backend v2.0")
    
    # Initialize config
    config = get_config()
    await config.load_all_configs()
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")

# Create FastAPI app
app = FastAPI(
    title="TramTue ChatBot AI Backend",
    description="Advanced AI Chatbot Backend với Multi-Agent System",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Get config
config = get_config()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
if config.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=config.ALLOWED_HOSTS
    )

# Request logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Request logging và timing"""
    start_time = time.time()
    
    # Generate correlation ID
    correlation_id = f"{int(time.time() * 1000)}-{hash(str(request.url)) % 10000}"
    
    # Add correlation ID to request state
    request.state.correlation_id = correlation_id
    
    # Log request
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        correlation_id=correlation_id,
        user_agent=request.headers.get("user-agent"),
        client_ip=request.client.host if request.client else None
    )
    
    try:
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=process_time,
            correlation_id=correlation_id
        )
        
        # Add headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log error
        logger.error(
            "Request failed",
            method=request.method,
            url=str(request.url),
            error=str(e),
            process_time=process_time,
            correlation_id=correlation_id
        )
        
        raise

# Rate limiting middleware (simple implementation)
@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    """Simple rate limiting"""
    # Skip rate limiting for health checks
    if request.url.path.startswith("/health"):
        return await call_next(request)
    
    # TODO: Implement proper rate limiting với Redis
    # For now, just pass through
    return await call_next(request)

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        url=str(request.url),
        correlation_id=correlation_id
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "correlation_id": correlation_id
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    
    logger.error(
        "Unhandled exception",
        error=str(exc),
        error_type=type(exc).__name__,
        url=str(request.url),
        correlation_id=correlation_id
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500,
            "correlation_id": correlation_id
        }
    )

# Include routers
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(rag.router)
    app.include_router(timers.router)
    app.include_router(admin.router)
    app.include_router(streaming.router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "TramTue ChatBot AI Backend",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

# Dependency injection for request logger
def get_request_logger(request: Request) -> RequestLogger:
    """Get request logger với correlation ID"""
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    return RequestLogger(correlation_id)

# Add dependency
app.dependency_overrides[RequestLogger] = get_request_logger

if __name__ == "__main__":
    import uvicorn
    
    # Development server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None  # Use our custom logging
    )