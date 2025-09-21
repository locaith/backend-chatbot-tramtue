"""
Supabase database client và operations
"""
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from supabase import create_client, Client
from postgrest import APIError
import structlog

from app.core.config import get_config
from app.models.database import *

logger = structlog.get_logger()

class DatabaseClient:
    """Supabase database client với async operations"""
    
    def __init__(self):
        config = get_config()
        self.client: Client = create_client(
            config.supabase_url,
            config.supabase_key
        )
        self.logger = logger.bind(component="database")
    
    async def _execute_query(self, query, operation: str = "query"):
        """Execute query với error handling"""
        try:
            result = query.execute()
            self.logger.info(f"Database {operation} successful", 
                           count=len(result.data) if result.data else 0)
            return result
        except APIError as e:
            self.logger.error(f"Database {operation} failed", 
                            error=str(e), code=e.code)
            raise
        except Exception as e:
            self.logger.error(f"Database {operation} error", error=str(e))
            raise
    
    # User operations
    async def create_user(self, user_data: UserCreate) -> User:
        """Tạo user mới"""
        data = user_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        
        result = await self._execute_query(
            self.client.table('users').insert(data),
            "create_user"
        )
        return User(**result.data[0])
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Lấy user theo ID"""
        result = await self._execute_query(
            self.client.table('users').select('*').eq('id', user_id),
            "get_user"
        )
        return User(**result.data[0]) if result.data else None
    
    async def get_user_by_phone(self, phone: str) -> Optional[User]:
        """Lấy user theo phone"""
        result = await self._execute_query(
            self.client.table('users').select('*').eq('phone', phone),
            "get_user_by_phone"
        )
        return User(**result.data[0]) if result.data else None
    
    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> User:
        """Update user"""
        updates['updated_at'] = datetime.utcnow().isoformat()
        result = await self._execute_query(
            self.client.table('users').update(updates).eq('id', user_id),
            "update_user"
        )
        return User(**result.data[0])
    
    # Conversation operations
    async def create_conversation(self, conv_data: ConversationCreate) -> Conversation:
        """Tạo conversation mới"""
        data = conv_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        data['last_message_at'] = datetime.utcnow().isoformat()
        
        result = await self._execute_query(
            self.client.table('conversations').insert(data),
            "create_conversation"
        )
        return Conversation(**result.data[0])
    
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Lấy conversation theo ID"""
        result = await self._execute_query(
            self.client.table('conversations').select('*').eq('id', conversation_id),
            "get_conversation"
        )
        return Conversation(**result.data[0]) if result.data else None
    
    async def get_user_conversations(self, user_id: str, limit: int = 10) -> List[Conversation]:
        """Lấy conversations của user"""
        result = await self._execute_query(
            self.client.table('conversations')
            .select('*')
            .eq('user_id', user_id)
            .order('last_message_at', desc=True)
            .limit(limit),
            "get_user_conversations"
        )
        return [Conversation(**row) for row in result.data]
    
    async def update_conversation(self, conversation_id: str, updates: Dict[str, Any]) -> Conversation:
        """Update conversation"""
        updates['updated_at'] = datetime.utcnow().isoformat()
        result = await self._execute_query(
            self.client.table('conversations').update(updates).eq('id', conversation_id),
            "update_conversation"
        )
        return Conversation(**result.data[0])
    
    # Message operations
    async def create_message(self, msg_data: MessageCreate) -> Message:
        """Tạo message mới"""
        data = msg_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        
        result = await self._execute_query(
            self.client.table('messages').insert(data),
            "create_message"
        )
        
        # Update conversation last_message_at
        await self.update_conversation(
            msg_data.conversation_id,
            {'last_message_at': datetime.utcnow().isoformat()}
        )
        
        return Message(**result.data[0])
    
    async def get_conversation_messages(self, conversation_id: str, limit: int = 50) -> List[Message]:
        """Lấy messages của conversation"""
        result = await self._execute_query(
            self.client.table('messages')
            .select('*')
            .eq('conversation_id', conversation_id)
            .order('created_at', desc=False)
            .limit(limit),
            "get_conversation_messages"
        )
        return [Message(**row) for row in result.data]
    
    # Memory operations
    async def create_memory(self, memory_data: MemoryCreate) -> Memory:
        """Tạo memory mới"""
        data = memory_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        
        result = await self._execute_query(
            self.client.table('memories').insert(data),
            "create_memory"
        )
        return Memory(**result.data[0])
    
    async def get_user_memories(self, user_id: str) -> List[Memory]:
        """Lấy memories của user"""
        result = await self._execute_query(
            self.client.table('memories')
            .select('*')
            .eq('user_id', user_id)
            .order('weight', desc=True),
            "get_user_memories"
        )
        return [Memory(**row) for row in result.data]
    
    async def update_memory(self, memory_id: str, updates: Dict[str, Any]) -> Memory:
        """Update memory"""
        updates['updated_at'] = datetime.utcnow().isoformat()
        result = await self._execute_query(
            self.client.table('memories').update(updates).eq('id', memory_id),
            "update_memory"
        )
        return Memory(**result.data[0])
    
    # Document operations
    async def create_document(self, doc_data: DocumentCreate) -> Document:
        """Tạo document mới"""
        data = doc_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        
        result = await self._execute_query(
            self.client.table('documents').insert(data),
            "create_document"
        )
        return Document(**result.data[0])
    
    async def get_document_by_hash(self, content_hash: str) -> Optional[Document]:
        """Lấy document theo content hash"""
        result = await self._execute_query(
            self.client.table('documents').select('*').eq('content_hash', content_hash),
            "get_document_by_hash"
        )
        return Document(**result.data[0]) if result.data else None
    
    async def create_doc_chunk(self, chunk_data: DocChunkCreate) -> DocChunk:
        """Tạo document chunk"""
        data = chunk_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        
        result = await self._execute_query(
            self.client.table('doc_chunks').insert(data),
            "create_doc_chunk"
        )
        return DocChunk(**result.data[0])
    
    async def create_doc_embedding(self, embedding_data: DocEmbeddingCreate) -> DocEmbedding:
        """Tạo document embedding"""
        data = embedding_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        
        result = await self._execute_query(
            self.client.table('doc_embeddings').insert(data),
            "create_doc_embedding"
        )
        return DocEmbedding(**result.data[0])
    
    async def vector_search(self, query_embedding: List[float], top_k: int = 5, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Vector similarity search"""
        try:
            # Sử dụng RPC function cho vector search
            result = self.client.rpc(
                'vector_search',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': threshold,
                    'match_count': top_k
                }
            ).execute()
            
            self.logger.info("Vector search completed", 
                           results_count=len(result.data))
            return result.data
        except Exception as e:
            self.logger.error("Vector search failed", error=str(e))
            raise
    
    # Timer operations
    async def create_timer(self, timer_data: TimerCreate) -> Timer:
        """Tạo timer mới"""
        data = timer_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        data['run_at'] = data['run_at'].isoformat()
        
        result = await self._execute_query(
            self.client.table('timers').insert(data),
            "create_timer"
        )
        return Timer(**result.data[0])
    
    async def get_pending_timers(self) -> List[Timer]:
        """Lấy pending timers"""
        now = datetime.utcnow().isoformat()
        result = await self._execute_query(
            self.client.table('timers')
            .select('*')
            .eq('status', 'pending')
            .lte('run_at', now)
            .order('run_at'),
            "get_pending_timers"
        )
        return [Timer(**row) for row in result.data]
    
    async def update_timer(self, timer_id: str, updates: Dict[str, Any]) -> Timer:
        """Update timer"""
        updates['updated_at'] = datetime.utcnow().isoformat()
        result = await self._execute_query(
            self.client.table('timers').update(updates).eq('id', timer_id),
            "update_timer"
        )
        return Timer(**result.data[0])
    
    # Handoff operations
    async def create_handoff(self, handoff_data: HandoffCreate) -> Handoff:
        """Tạo handoff mới"""
        data = handoff_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        
        result = await self._execute_query(
            self.client.table('handoffs').insert(data),
            "create_handoff"
        )
        return Handoff(**result.data[0])
    
    async def get_pending_handoffs(self) -> List[Handoff]:
        """Lấy pending handoffs"""
        result = await self._execute_query(
            self.client.table('handoffs')
            .select('*')
            .is_('resolved_at', 'null')
            .order('created_at'),
            "get_pending_handoffs"
        )
        return [Handoff(**row) for row in result.data]
    
    # Metrics operations
    async def create_metric(self, metric_data: MetricCreate) -> Metric:
        """Tạo metric mới"""
        data = metric_data.model_dump()
        data['id'] = str(uuid.uuid4())
        data['created_at'] = datetime.utcnow().isoformat()
        data['updated_at'] = datetime.utcnow().isoformat()
        data['timestamp'] = datetime.utcnow().isoformat()
        
        result = await self._execute_query(
            self.client.table('metrics').insert(data),
            "create_metric"
        )
        return Metric(**result.data[0])

# Global database instance
_db_client = None

def get_db() -> DatabaseClient:
    """Get database client instance"""
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client