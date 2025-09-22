"""
Streaming API endpoints for real-time chat with human-like timing
"""
import asyncio
import json
from typing import AsyncGenerator, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import structlog

from app.services.orchestrator import get_orchestrator
from app.services.human_timing import get_timing_service
from app.models.database import SendMessageRequest
from app.core.logging import get_request_logger

router = APIRouter(prefix="/streaming", tags=["streaming"])
logger = structlog.get_logger()

@router.post("/chat")
async def stream_chat_response(
    request: SendMessageRequest,
    req: Request,
    request_logger=Depends(get_request_logger)
):
    """Stream chat response with human-like timing"""
    
    try:
        orchestrator = get_orchestrator()
        timing_service = get_timing_service()
        
        # Process message to get response
        response_data = await orchestrator.process_message(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            message=request.message,
            context=request.context
        )
        
        # Create streaming generator
        async def generate_stream():
            try:
                # Send initial typing indicator
                yield {
                    "event": "typing_start",
                    "data": {
                        "agent_type": response_data["agent_type"],
                        "estimated_delay": response_data["metadata"]["typing_delay"]
                    }
                }
                
                # Get message chunks and timing
                chunks = response_data["metadata"]["message_chunks"]
                total_delay = response_data["metadata"]["typing_delay"]
                
                # Distribute delay across chunks
                chunk_delays = timing_service._distribute_delay(chunks, total_delay)
                
                # Stream chunks with realistic timing
                for i, (chunk, delay) in enumerate(zip(chunks, chunk_delays)):
                    # Wait for typing delay
                    await asyncio.sleep(delay)
                    
                    # Send chunk
                    yield {
                        "event": "message_chunk",
                        "data": {
                            "chunk": chunk,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "is_final": i == len(chunks) - 1,
                            "agent_type": response_data["agent_type"]
                        }
                    }
                
                # Send completion event
                yield {
                    "event": "message_complete",
                    "data": {
                        "agent_type": response_data["agent_type"],
                        "confidence": response_data["confidence"],
                        "metadata": response_data["metadata"]
                    }
                }
                
            except Exception as e:
                logger.error("Error in stream generation", error=str(e))
                yield {
                    "event": "error",
                    "data": {
                        "error": "Stream generation failed",
                        "details": str(e)
                    }
                }
        
        # Return Server-Sent Events response
        return EventSourceResponse(
            generate_sse_stream(generate_stream()),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control"
            }
        )
        
    except Exception as e:
        logger.error("Error in streaming chat", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/typing-simulation")
async def simulate_typing_only(
    request: Dict[str, Any],
    req: Request,
    request_logger=Depends(get_request_logger)
):
    """Simulate typing for a given message without processing"""
    
    try:
        timing_service = get_timing_service()
        
        message = request.get("message", "")
        agent_type = request.get("agent_type", "general_chat")
        
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Calculate timing data
        timing_data = await timing_service.simulate_typing(message, agent_type)
        
        # Create streaming generator for typing simulation
        async def generate_typing_stream():
            try:
                chunks = timing_data["chunks"]
                total_delay = timing_data["total_delay"]
                
                # Send start event
                yield {
                    "event": "typing_start",
                    "data": {
                        "total_delay": total_delay,
                        "complexity": timing_data["complexity"],
                        "pattern": timing_data["pattern"],
                        "chunk_count": len(chunks)
                    }
                }
                
                # Distribute delay across chunks
                chunk_delays = timing_service._distribute_delay(chunks, total_delay)
                
                # Stream typing simulation
                for i, (chunk, delay) in enumerate(zip(chunks, chunk_delays)):
                    # Wait for typing delay
                    await asyncio.sleep(delay)
                    
                    # Send typing progress
                    yield {
                        "event": "typing_progress",
                        "data": {
                            "chunk": chunk,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "delay_used": delay,
                            "is_final": i == len(chunks) - 1
                        }
                    }
                
                # Send completion
                yield {
                    "event": "typing_complete",
                    "data": {
                        "total_time": total_delay,
                        "message": message
                    }
                }
                
            except Exception as e:
                logger.error("Error in typing simulation", error=str(e))
                yield {
                    "event": "error",
                    "data": {
                        "error": "Typing simulation failed",
                        "details": str(e)
                    }
                }
        
        return EventSourceResponse(
            generate_sse_stream(generate_typing_stream()),
            media_type="text/plain"
        )
        
    except Exception as e:
        logger.error("Error in typing simulation", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

async def generate_sse_stream(generator: AsyncGenerator[Dict[str, Any], None]):
    """Convert async generator to SSE format"""
    
    async for event_data in generator:
        event = event_data.get("event", "message")
        data = event_data.get("data", {})
        
        # Format as SSE
        sse_data = f"event: {event}\n"
        sse_data += f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        
        yield sse_data

@router.get("/health")
async def streaming_health():
    """Health check for streaming endpoints"""
    return {
        "status": "healthy",
        "service": "streaming",
        "features": [
            "real_time_chat",
            "human_timing",
            "message_chunking",
            "typing_simulation"
        ]
    }