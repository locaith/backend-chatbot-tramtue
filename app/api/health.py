"""
Health check endpoints
"""
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
import structlog

from app.core.config import get_config
from app.core.database import get_db
from app.services.rag import get_rag_service
from app.services.memory import get_memory_engine

logger = structlog.get_logger()
router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def health_check() -> Dict[str, Any]:
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "TramTue ChatBot AI Backend",
        "version": "2.0.0"
    }

@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check với dependencies"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "TramTue ChatBot AI Backend",
        "version": "2.0.0",
        "components": {}
    }
    
    try:
        # Check config
        config = get_config()
        health_status["components"]["config"] = {
            "status": "healthy",
            "environment": config.ENVIRONMENT
        }
        
        # Check database connection
        try:
            db = get_db()
            # Simple query to test connection
            result = await db.supabase.table("users").select("id").limit(1).execute()
            health_status["components"]["database"] = {
                "status": "healthy",
                "connection": "active"
            }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Check RAG service
        try:
            rag_service = get_rag_service()
            health_status["components"]["rag"] = {
                "status": "healthy",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
            }
        except Exception as e:
            health_status["components"]["rag"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Check memory engine
        try:
            memory_engine = get_memory_engine()
            health_status["components"]["memory"] = {
                "status": "healthy"
            }
        except Exception as e:
            health_status["components"]["memory"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "degraded"
        
        # Check Gemini API (if configured)
        if config.GEMINI_API_KEY:
            health_status["components"]["gemini"] = {
                "status": "configured"
            }
        else:
            health_status["components"]["gemini"] = {
                "status": "not_configured"
            }
            health_status["status"] = "degraded"
        
        logger.info("Health check completed", status=health_status["status"])
        return health_status
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check cho Kubernetes/Docker"""
    try:
        # Check critical dependencies
        config = get_config()
        db = get_db()
        
        # Test database connection
        await db.supabase.table("users").select("id").limit(1).execute()
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/live")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check cho Kubernetes/Docker"""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }