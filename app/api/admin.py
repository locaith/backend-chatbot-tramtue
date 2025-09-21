"""
Admin endpoints cho management và monitoring
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

from app.core.config import get_config
from app.core.database import get_db
from app.services.rag import get_rag_service
from app.services.memory import get_memory_engine
from app.core.logging import RequestLogger

logger = structlog.get_logger()
router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBearer()

async def verify_admin_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify admin token"""
    config = get_config()
    if credentials.credentials != config.ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return credentials.credentials

@router.post("/reload")
async def reload_configurations(
    admin_token: str = Depends(verify_admin_token),
    request_logger: RequestLogger = Depends()
) -> Dict[str, Any]:
    """Reload tất cả configurations"""
    try:
        config = get_config()
        
        # Reload config
        await config.reload_config()
        
        # Reload prompts
        await config.reload_prompts()
        
        # Reload policies
        await config.reload_policies()
        
        # Reload RAG config
        await config.reload_rag_config()
        
        await request_logger.log_event(
            "admin_reload",
            {"components": ["config", "prompts", "policies", "rag_config"]}
        )
        
        return {
            "success": True,
            "reloaded": ["config", "prompts", "policies", "rag_config"],
            "timestamp": config.get_current_time().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to reload configurations", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reload configurations")

@router.get("/stats")
async def get_system_stats(
    admin_token: str = Depends(verify_admin_token),
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Lấy system statistics"""
    try:
        # Database stats
        users_count = await db.count_users()
        conversations_count = await db.count_conversations()
        messages_count = await db.count_messages()
        memories_count = await db.count_memories()
        documents_count = await db.count_documents()
        
        # RAG stats
        rag_service = get_rag_service()
        rag_stats = await rag_service.get_stats()
        
        return {
            "database": {
                "users": users_count,
                "conversations": conversations_count,
                "messages": messages_count,
                "memories": memories_count,
                "documents": documents_count
            },
            "rag": rag_stats,
            "timestamp": get_config().get_current_time().isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to get system stats", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get system stats")

@router.get("/users")
async def list_users(
    admin_token: str = Depends(verify_admin_token),
    limit: int = 50,
    offset: int = 0,
    db = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List users với pagination"""
    try:
        users = await db.list_users(limit, offset)
        
        return [
            {
                "id": user.id,
                "phone": user.phone,
                "name": user.name,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "metadata": user.metadata
            }
            for user in users
        ]
        
    except Exception as e:
        logger.error("Failed to list users", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list users")

@router.get("/conversations")
async def list_conversations(
    admin_token: str = Depends(verify_admin_token),
    limit: int = 50,
    offset: int = 0,
    state: Optional[ConversationState] = None,
    agent_type: Optional[AgentType] = None,
    db = Depends(get_db)
) -> List[Dict[str, Any]]:
    """List conversations với filtering"""
    try:
        conversations = await db.list_conversations(limit, offset, state, agent_type)
        
        return [
            {
                "id": conv.id,
                "user_id": conv.user_id,
                "agent_type": conv.agent_type,
                "state": conv.state,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "metadata": conv.metadata
            }
            for conv in conversations
        ]
        
    except Exception as e:
        logger.error("Failed to list conversations", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list conversations")

@router.get("/metrics")
async def get_metrics(
    admin_token: str = Depends(verify_admin_token),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Lấy metrics và analytics"""
    try:
        from datetime import datetime, timedelta
        
        # Default to last 7 days
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
        if not end_date:
            end_date = datetime.utcnow().isoformat()
        
        metrics = await db.get_metrics(start_date, end_date)
        
        # Aggregate metrics
        aggregated = {
            "total_conversations": 0,
            "total_messages": 0,
            "avg_response_time": 0,
            "agent_usage": {},
            "daily_stats": []
        }
        
        for metric in metrics:
            aggregated["total_conversations"] += metric.conversation_count
            aggregated["total_messages"] += metric.message_count
            
            agent_type = metric.metadata.get("agent_type", "unknown")
            if agent_type not in aggregated["agent_usage"]:
                aggregated["agent_usage"][agent_type] = 0
            aggregated["agent_usage"][agent_type] += metric.conversation_count
        
        if metrics:
            aggregated["avg_response_time"] = sum(
                m.metadata.get("avg_response_time", 0) for m in metrics
            ) / len(metrics)
        
        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date
            },
            "metrics": aggregated,
            "raw_metrics": [
                {
                    "date": metric.date,
                    "conversation_count": metric.conversation_count,
                    "message_count": metric.message_count,
                    "metadata": metric.metadata
                }
                for metric in metrics
            ]
        }
        
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get metrics")

@router.post("/users/{user_id}/reset")
async def reset_user_data(
    user_id: str,
    admin_token: str = Depends(verify_admin_token),
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Reset user data (memories, conversations)"""
    try:
        user = await db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete user memories
        await db.delete_user_memories(user_id)
        
        # Archive user conversations
        await db.archive_user_conversations(user_id)
        
        return {
            "success": True,
            "user_id": user_id,
            "reset_components": ["memories", "conversations"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to reset user data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to reset user data")

@router.post("/cleanup")
async def cleanup_old_data(
    admin_token: str = Depends(verify_admin_token),
    days_old: int = 30,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Cleanup old data"""
    try:
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Cleanup old conversations
        deleted_conversations = await db.cleanup_old_conversations(cutoff_date)
        
        # Cleanup old messages
        deleted_messages = await db.cleanup_old_messages(cutoff_date)
        
        # Cleanup old metrics
        deleted_metrics = await db.cleanup_old_metrics(cutoff_date)
        
        return {
            "success": True,
            "cutoff_date": cutoff_date.isoformat(),
            "deleted": {
                "conversations": deleted_conversations,
                "messages": deleted_messages,
                "metrics": deleted_metrics
            }
        }
        
    except Exception as e:
        logger.error("Failed to cleanup old data", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to cleanup old data")