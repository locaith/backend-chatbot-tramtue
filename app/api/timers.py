"""
Timer endpoints cho scheduled tasks
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from datetime import datetime, timedelta
import structlog

from app.models.database import *
from app.core.database import get_db
from app.core.logging import RequestLogger

logger = structlog.get_logger()
router = APIRouter(prefix="/timers", tags=["timers"])

@router.post("/run")
async def run_scheduled_tasks(
    background_tasks: BackgroundTasks,
    db = Depends(get_db),
    request_logger: RequestLogger = Depends()
) -> Dict[str, Any]:
    """Chạy scheduled tasks (được gọi bởi cron job)"""
    try:
        # Get pending timers
        current_time = datetime.utcnow()
        pending_timers = await db.get_pending_timers(current_time)
        
        executed_count = 0
        failed_count = 0
        
        for timer in pending_timers:
            try:
                # Execute timer task in background
                background_tasks.add_task(execute_timer_task, timer.id)
                executed_count += 1
                
                # Mark timer as executed
                await db.update_timer(timer.id, {
                    "status": TimerStatus.EXECUTED,
                    "executed_at": current_time
                })
                
            except Exception as e:
                failed_count += 1
                logger.error("Timer execution failed", 
                           timer_id=timer.id, 
                           error=str(e))
                
                # Mark timer as failed
                await db.update_timer(timer.id, {
                    "status": TimerStatus.FAILED,
                    "executed_at": current_time,
                    "metadata": {**timer.metadata, "error": str(e)}
                })
        
        await request_logger.log_event(
            "timers_executed",
            {
                "total_pending": len(pending_timers),
                "executed": executed_count,
                "failed": failed_count
            }
        )
        
        return {
            "success": True,
            "total_pending": len(pending_timers),
            "executed": executed_count,
            "failed": failed_count,
            "timestamp": current_time.isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to run scheduled tasks", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to run scheduled tasks")

@router.post("/", response_model=TimerResponse)
async def create_timer(
    request: TimerCreate,
    db = Depends(get_db)
) -> TimerResponse:
    """Tạo timer mới"""
    try:
        timer = await db.create_timer(request)
        
        return TimerResponse(
            id=timer.id,
            user_id=timer.user_id,
            conversation_id=timer.conversation_id,
            timer_type=timer.timer_type,
            scheduled_time=timer.scheduled_time,
            status=timer.status,
            created_at=timer.created_at,
            metadata=timer.metadata
        )
        
    except Exception as e:
        logger.error("Failed to create timer", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create timer")

@router.get("/user/{user_id}")
async def get_user_timers(
    user_id: str,
    status: Optional[TimerStatus] = None,
    limit: int = 50,
    offset: int = 0,
    db = Depends(get_db)
) -> List[TimerResponse]:
    """Lấy timers của user"""
    try:
        timers = await db.get_user_timers(user_id, status, limit, offset)
        
        return [
            TimerResponse(
                id=timer.id,
                user_id=timer.user_id,
                conversation_id=timer.conversation_id,
                timer_type=timer.timer_type,
                scheduled_time=timer.scheduled_time,
                status=timer.status,
                created_at=timer.created_at,
                executed_at=timer.executed_at,
                metadata=timer.metadata
            )
            for timer in timers
        ]
        
    except Exception as e:
        logger.error("Failed to get user timers", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get user timers")

@router.put("/{timer_id}")
async def update_timer(
    timer_id: str,
    request: TimerUpdate,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Update timer"""
    try:
        timer = await db.get_timer(timer_id)
        if not timer:
            raise HTTPException(status_code=404, detail="Timer not found")
        
        update_data = {}
        if request.scheduled_time is not None:
            update_data["scheduled_time"] = request.scheduled_time
        if request.status is not None:
            update_data["status"] = request.status
        if request.metadata is not None:
            update_data["metadata"] = request.metadata
        
        updated_timer = await db.update_timer(timer_id, update_data)
        
        return {
            "success": True,
            "timer_id": timer_id,
            "updated_fields": list(update_data.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update timer", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update timer")

@router.delete("/{timer_id}")
async def cancel_timer(
    timer_id: str,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Cancel timer"""
    try:
        timer = await db.get_timer(timer_id)
        if not timer:
            raise HTTPException(status_code=404, detail="Timer not found")
        
        if timer.status == TimerStatus.EXECUTED:
            raise HTTPException(status_code=400, detail="Cannot cancel executed timer")
        
        await db.update_timer(timer_id, {
            "status": TimerStatus.CANCELLED,
            "executed_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "timer_id": timer_id,
            "status": "cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel timer", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to cancel timer")

async def execute_timer_task(timer_id: str):
    """Execute timer task"""
    try:
        db = get_db()
        timer = await db.get_timer(timer_id)
        
        if not timer:
            logger.error("Timer not found for execution", timer_id=timer_id)
            return
        
        # Import here để tránh circular imports
        from app.services.orchestrator import get_orchestrator
        
        orchestrator = get_orchestrator()
        
        # Execute based on timer type
        if timer.timer_type == TimerType.FOLLOWUP:
            await orchestrator.execute_followup_timer(timer)
        elif timer.timer_type == TimerType.REMINDER:
            await orchestrator.execute_reminder_timer(timer)
        elif timer.timer_type == TimerType.HANDOFF:
            await orchestrator.execute_handoff_timer(timer)
        else:
            logger.warning("Unknown timer type", 
                         timer_id=timer_id, 
                         timer_type=timer.timer_type)
        
        logger.info("Timer task executed successfully", timer_id=timer_id)
        
    except Exception as e:
        logger.error("Timer task execution failed", 
                    timer_id=timer_id, 
                    error=str(e))