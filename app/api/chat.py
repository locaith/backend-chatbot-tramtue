"""
Chat endpoints cho AI Agent
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional, Annotated, TYPE_CHECKING
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import structlog
import json
import asyncio

from app.models.database import *
from app.core.database import get_db

if TYPE_CHECKING:
    from app.core.database import DatabaseClient
from app.services.memory import get_memory_engine
from app.services.discovery import DiscoveryAgent
from app.services.orchestrator import get_orchestrator
from app.core.logging import RequestLogger

logger = structlog.get_logger()
router = APIRouter(prefix="/chat", tags=["chat"])

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate,
    db: Annotated["DatabaseClient", Depends(get_db)] = Depends(get_db),
    request_logger: RequestLogger = Depends()
) -> ConversationResponse:
    """Tạo conversation mới"""
    try:
        # Tạo hoặc lấy user
        user = await db.get_user_by_phone(request.user_phone)
        if not user:
            user_data = UserCreate(
                phone=request.user_phone,
                name=request.user_name,
                metadata=request.user_metadata or {}
            )
            user = await db.create_user(user_data)
        
        # Tạo conversation
        conversation_data = ConversationCreate(
            user_id=user.id,
            agent_type=request.agent_type,
            metadata=request.metadata or {}
        )
        conversation = await db.create_conversation(conversation_data)
        
        await request_logger.log_event(
            "conversation_created",
            {"conversation_id": conversation.id, "user_id": user.id}
        )
        
        return ConversationResponse(
            id=conversation.id,
            user_id=user.id,
            agent_type=conversation.agent_type,
            state=conversation.state,
            created_at=conversation.created_at,
            metadata=conversation.metadata
        )
        
    except Exception as e:
        logger.error("Failed to create conversation", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create conversation")

@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    db: Annotated["DatabaseClient", Depends(get_db)] = Depends(get_db),
    memory_engine = Depends(get_memory_engine),
    logger: RequestLogger = Depends()
):
    """Gửi tin nhắn và nhận phản hồi từ AI"""
    
    try:
        # Validate conversation exists
        conversation = await db.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Save user message
        user_message = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=request.message,
            metadata=request.metadata or {}
        )
        await db.create_message(user_message)
        
        # Process with Orchestrator
        orchestrator = get_orchestrator()
        response_data = await orchestrator.process_message(
            user_id=conversation.user_id,
            conversation_id=conversation_id,
            message=request.message,
            context=request.metadata
        )
        
        # Save AI response
        ai_message = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=response_data["response"],
            metadata={
                "agent": response_data["agent"],
                "typing_delay": response_data.get("typing_delay", 0),
                **{k: v for k, v in response_data.items() if k not in ["response", "agent"]}
            }
        )
        await db.create_message(ai_message)
        
        logger.info(
            "Message processed successfully",
            conversation_id=conversation_id,
            user_message_length=len(request.message),
            ai_response_length=len(response_data["response"]),
            agent=response_data["agent"],
            typing_delay=response_data.get("typing_delay", 0)
        )
        
        return SendMessageResponse(
            message_id=ai_message.id,
            response=response_data["response"],
            agent=response_data["agent"],
            metadata={
                **ai_message.metadata,
                "supports_streaming": True,
                "streaming_endpoint": "/streaming/chat"
            }
        )
        
    except Exception as e:
        logger.error("Error sending message", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: str,
    limit: int = 50,
    offset: int = 0,
    db: Annotated["DatabaseClient", Depends(get_db)] = Depends(get_db)
) -> List[MessageResponse]:
    """Lấy messages của conversation"""
    try:
        # Validate conversation
        conversation = await db.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = await db.get_conversation_messages(conversation_id, limit, offset)
        
        return [
            MessageResponse(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                metadata=msg.metadata
            )
            for msg in messages
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get messages", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get messages")

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: Annotated["DatabaseClient", Depends(get_db)] = Depends(get_db)
) -> ConversationResponse:
    """Lấy thông tin conversation"""
    try:
        conversation = await db.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        return ConversationResponse(
            id=conversation.id,
            user_id=conversation.user_id,
            agent_type=conversation.agent_type,
            state=conversation.state,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            metadata=conversation.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get conversation", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get conversation")

@router.put("/conversations/{conversation_id}/state")
async def update_conversation_state(
    conversation_id: str,
    request: ConversationStateUpdate,
    db: Annotated["DatabaseClient", Depends(get_db)] = Depends(get_db)
) -> Dict[str, Any]:
    """Update conversation state"""
    try:
        conversation = await db.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        updated_conversation = await db.update_conversation(
            conversation_id,
            {"state": request.state, "metadata": request.metadata}
        )
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "new_state": updated_conversation.state
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update conversation state", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update conversation state")

@router.get("/users/{user_id}/conversations", response_model=List[ConversationResponse])
async def get_user_conversations(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    db: Annotated["DatabaseClient", Depends(get_db)] = Depends(get_db)
) -> List[ConversationResponse]:
    """Lấy danh sách conversations của user"""
    try:
        user = await db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        conversations = await db.get_user_conversations(user_id, limit, offset)
        
        return [
            ConversationResponse(
                id=conv.id,
                user_id=conv.user_id,
                agent_type=conv.agent_type,
                state=conv.state,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                metadata=conv.metadata
            )
            for conv in conversations
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user conversations", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get user conversations")

@router.get("/users/{user_id}/profile")
async def get_user_profile(
    user_id: str,
    db: Annotated["DatabaseClient", Depends(get_db)] = Depends(get_db)
) -> Dict[str, Any]:
    """Lấy user profile từ memory engine"""
    try:
        user = await db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get profile từ discovery agent
        discovery_agent = get_discovery_agent()
        profile_analysis = await discovery_agent.analyze_user_profile(user_id)
        
        return {
            "user_id": user_id,
            "user_info": {
                "id": user.id,
                "phone": user.phone,
                "name": user.name,
                "created_at": user.created_at
            },
            "profile_analysis": profile_analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user profile", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get user profile")

@router.post("/users/{user_id}/memories")
async def create_memory(
    user_id: str,
    request: MemoryCreate,
    db: Annotated["DatabaseClient", Depends(get_db)] = Depends(get_db)
) -> Dict[str, Any]:
    """Tạo memory mới cho user"""
    try:
        user = await db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        memory = await db.create_memory(request)
        
        return {
            "success": True,
            "memory_id": memory.id,
            "key": memory.key,
            "value": memory.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create memory", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create memory")

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Annotated["DatabaseClient", Depends(get_db)] = Depends(get_db)
) -> Dict[str, str]:
    """Delete a conversation"""
    try:
        conversation = await db.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        await db.delete_conversation(conversation_id)
        
        return {
            "success": "true",
            "message": "Conversation deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete conversation", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete conversation")

async def process_message_async(conversation_id: str, message_id: str, content: str):
    """Process message asynchronously"""
    try:
        # Import here để tránh circular imports
        from app.services.orchestrator import get_orchestrator
        
        db = get_db()
        memory_engine = get_memory_engine()
        discovery_agent = get_discovery_agent()
        orchestrator = get_orchestrator()
        
        # Get conversation và user
        conversation = await db.get_conversation(conversation_id)
        user = await db.get_user(conversation.user_id)
        
        # Extract memories từ user message
        await memory_engine.extract_and_store_memories(
            user_id=user.id,
            conversation_text=content,
            source=f"conversation_{conversation_id}"
        )
        
        # Process với discovery agent nếu cần
        if conversation.agent_type == AgentType.DISCOVERY:
            await discovery_agent.process_user_response(
                user_id=user.id,
                message=content,
                conversation_id=conversation_id
            )
        
        # Generate AI response
        ai_response = await orchestrator.process_message(
            conversation_id=conversation_id,
            user_message=content,
            user_id=user.id
        )
        
        # Store AI response
        ai_message_data = MessageCreate(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=ai_response["content"],
            metadata=ai_response.get("metadata", {})
        )
        await db.create_message(ai_message_data)
        
        logger.info("Message processed successfully", 
                   conversation_id=conversation_id,
                   message_id=message_id)
        
    except Exception as e:
        logger.error("Failed to process message async", 
                    conversation_id=conversation_id,
                    error=str(e))