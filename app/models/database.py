"""
Database models và schemas với Pydantic v2
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field
import uuid

# Enums
class ConversationState(str, Enum):
    ACTIVE = "active"
    HANDOFF = "handoff"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class AgentType(str, Enum):
    DISCOVERY = "discovery"
    CSKH = "cskh"
    SALES = "sales"
    HANDOFF = "handoff"
    FOLLOWUP = "followup"

class TimerStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class HandoffReason(str, Enum):
    PREGNANCY_OR_CHILDREN = "pregnancy_or_children"
    ALLERGY_CONCERN = "allergy_concern"
    PAYMENT_ISSUE = "payment_issue"
    SHIPPING_ISSUE = "shipping_issue"
    COMPLEX_COMPLAINT = "complex_complaint"
    ESCALATION_REQUEST = "escalation_request"

# Base Models
class BaseDBModel(BaseModel):
    """Base model cho tất cả database entities"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# User Models
class User(BaseDBModel):
    """User model"""
    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    preferred_name: Optional[str] = None
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)

class UserCreate(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    preferred_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Conversation Models
class Conversation(BaseDBModel):
    """Conversation model"""
    user_id: str
    state: ConversationState = ConversationState.ACTIVE
    title: Optional[str] = None
    summary: Optional[str] = None
    last_message_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ConversationCreate(BaseModel):
    """Request model for creating conversation"""
    user_id: str
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ConversationResponse(BaseModel):
    """Response model for conversation"""
    id: str
    user_id: str
    title: str
    state: ConversationState
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

# Message Models
class Message(BaseDBModel):
    """Message model"""
    conversation_id: str
    role: MessageRole
    content: str
    agent_type: Optional[AgentType] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    processing_time_ms: Optional[float] = None
    used_rag: bool = False
    used_serper: bool = False
    rag_sources: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MessageCreate(BaseModel):
    """Request model for creating message"""
    conversation_id: str
    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = None

class MessageResponse(BaseModel):
    """Response model for message"""
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    created_at: datetime
    metadata: Dict[str, Any]

class SendMessageRequest(BaseModel):
    """Request model for sending message"""
    message: str
    metadata: Optional[Dict[str, Any]] = None

class SendMessageResponse(BaseModel):
    """Response model for AI message"""
    message_id: str
    response: str
    agent: str
    metadata: Dict[str, Any]

# Memory Models
class Memory(BaseDBModel):
    """User memory model"""
    user_id: str
    key: str
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str  # discovery, conversation, explicit
    needs_confirmation: bool = False
    confirmed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class MemoryCreate(BaseModel):
    user_id: str
    key: str
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str
    needs_confirmation: bool = False
    expires_at: Optional[datetime] = None

# Document Models
class Document(BaseDBModel):
    """Document model cho RAG"""
    source_type: str  # website, file, manual
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    title: str
    content_hash: str
    total_chunks: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocumentCreate(BaseModel):
    source_type: str
    source_url: Optional[str] = None
    source_path: Optional[str] = None
    title: str
    content_hash: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocChunk(BaseDBModel):
    """Document chunk model"""
    document_id: str
    chunk_index: int
    content: str
    content_hash: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocChunkCreate(BaseModel):
    document_id: str
    chunk_index: int
    content: str
    content_hash: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocEmbedding(BaseDBModel):
    """Document embedding model"""
    chunk_id: str
    embedding: List[float]
    model_name: str
    dimension: int

class DocEmbeddingCreate(BaseModel):
    chunk_id: str
    embedding: List[float]
    model_name: str
    dimension: int

# Timer Models
class Timer(BaseDBModel):
    """Timer model cho follow-up"""
    user_id: str
    conversation_id: str
    timer_type: str  # followup, reminder, escalation
    run_at: datetime
    status: TimerStatus = TimerStatus.PENDING
    payload: Dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    max_attempts: int = 3
    last_attempt_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class TimerCreate(BaseModel):
    user_id: str
    conversation_id: str
    timer_type: str
    run_at: datetime
    payload: Dict[str, Any] = Field(default_factory=dict)
    max_attempts: int = 3

# Handoff Models
class Handoff(BaseDBModel):
    """Handoff model"""
    user_id: str
    conversation_id: str
    reason: HandoffReason
    description: str
    priority: str = "normal"  # low, normal, high, urgent
    assigned_to: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class HandoffCreate(BaseModel):
    user_id: str
    conversation_id: str
    reason: HandoffReason
    description: str
    priority: str = "normal"
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Metrics Models
class Metric(BaseDBModel):
    """Metrics model"""
    metric_type: str  # chat_request, chat_response, rag_search, error
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    value: float
    unit: str
    tags: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class MetricCreate(BaseModel):
    metric_type: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    value: float
    unit: str
    tags: Dict[str, str] = Field(default_factory=dict)

# API Request/Response Models
class ChatRequest(BaseModel):
    """Chat API request model"""
    message: str = Field(..., min_length=1, max_length=4000)
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    force_model: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)

class MessagePart(BaseModel):
    """Message part cho human-like response"""
    text: str
    delay_ms: int = 0

class ChatResponse(BaseModel):
    """Chat API response model"""
    conversation_id: str
    message_id: str
    parts: List[MessagePart]
    agent_type: AgentType
    model_used: str
    processing_time_ms: float
    used_rag: bool = False
    used_serper: bool = False
    rag_sources: List[str] = Field(default_factory=list)
    handoff_triggered: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RAGSearchRequest(BaseModel):
    """RAG search request"""
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)

class RAGSearchResult(BaseModel):
    """RAG search result"""
    chunk_id: str
    content: str
    score: float
    document_title: str
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class RAGSearchResponse(BaseModel):
    """RAG search response"""
    results: List[RAGSearchResult]
    total_found: int
    query_time_ms: float

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "ok"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    services: Dict[str, str] = Field(default_factory=dict)