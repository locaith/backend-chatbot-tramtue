"""
Orchestrator - Multi-Agent System Controller
"""
import asyncio
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import structlog
import google.generativeai as genai
from datetime import datetime, timedelta

from app.core.config import get_config
from app.core.database import get_db
from app.models.database import (
    Message, MessageRole, AgentType, ConversationState,
    HandoffRequest, HandoffStatus
)
from app.services.memory import MemoryEngine, get_memory_engine
from app.services.discovery import DiscoveryAgent
from app.services.rag import get_rag_service
from app.services.human_timing import get_timing_service, MessageComplexity, TypingPattern

logger = structlog.get_logger()

class AgentDecision(Enum):
    """Agent routing decisions"""
    DISCOVERY = "discovery"
    CUSTOMER_SERVICE = "customer_service"
    SALES = "sales"
    HANDOFF_HUMAN = "handoff_human"
    FOLLOWUP = "followup"
    GENERAL_CHAT = "general_chat"

class MessageType(Enum):
    """Message types for processing"""
    GREETING = "greeting"
    QUESTION = "question"
    COMPLAINT = "complaint"
    PURCHASE_INTENT = "purchase_intent"
    PERSONAL_INFO = "personal_info"
    FOLLOWUP = "followup"
    GOODBYE = "goodbye"

class Orchestrator:
    """Main orchestrator for multi-agent system"""
    
    def __init__(self):
        self.config = get_config()
        self.db = get_db()
        self.memory_engine = get_memory_engine()
        self.rag_service = get_rag_service()
        self.discovery_agent = DiscoveryAgent()
        self.timing_service = get_timing_service()
        
        # Initialize Gemini client
        genai.configure(api_key=self.config.gemini_api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        
        # Agent prompts
        self.agent_prompts = {
            AgentDecision.DISCOVERY: self._get_discovery_prompt(),
            AgentDecision.CUSTOMER_SERVICE: self._get_customer_service_prompt(),
            AgentDecision.SALES: self._get_sales_prompt(),
            AgentDecision.FOLLOWUP: self._get_followup_prompt(),
            AgentDecision.GENERAL_CHAT: self._get_general_chat_prompt()
        }
        
        # Typing simulation settings
        self.typing_speed = 50  # characters per second
        self.min_delay = 1.0    # minimum delay in seconds
        self.max_delay = 3.0    # maximum delay in seconds
        
    async def process_message(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Process incoming message through multi-agent system"""
        
        logger.info(
            "Processing message",
            user_id=user_id,
            conversation_id=conversation_id,
            message_length=len(message)
        )
        
        try:
            # 1. Analyze message and determine routing
            message_analysis = await self._analyze_message(message, context)
            agent_decision = await self._route_to_agent(message_analysis, user_id, conversation_id)
            
            # 2. Get user memory context
            memory_context = await self.memory_engine.get_context(user_id, conversation_id)
            
            # 3. Get RAG context if needed
            rag_context = ""
            if agent_decision in [AgentDecision.CUSTOMER_SERVICE, AgentDecision.SALES]:
                rag_context = await self.rag_service.get_context_for_query(message)
            
            # 4. Process with appropriate agent
            response_data = await self._process_with_agent(
                agent_decision,
                message,
                user_id,
                conversation_id,
                memory_context,
                rag_context,
                message_analysis
            )
            
            # 5. Calculate human-like timing
            timing_data = await self.timing_service.simulate_typing(
                response_data.get("response", ""),
                agent_decision.value
            )
            
            # 6. Update memory
            await self.memory_engine.process_interaction(
                user_id,
                conversation_id,
                message,
                response_data.get("response", ""),
                {
                    "agent": agent_decision.value,
                    "message_type": message_analysis.get("type"),
                    "intent": message_analysis.get("intent"),
                    "sentiment": message_analysis.get("sentiment")
                }
            )
            
            # 7. Add timing data to response
            response_data.update({
                "typing_delay": timing_data["total_delay"],
                "message_complexity": timing_data["complexity"],
                "typing_pattern": timing_data["pattern"],
                "message_chunks": timing_data["chunks"]
            })
            
            return response_data
            
        except Exception as e:
            logger.error("Error processing message", error=str(e))
            
            # Calculate timing for fallback
            fallback_response = "Xin lỗi, tôi đang gặp một chút vấn đề. Bạn có thể thử lại không?"
            timing_data = await self.timing_service.simulate_typing(
                fallback_response,
                "error_handler"
            )
            
            return {
                "response": fallback_response,
                "agent": AgentDecision.GENERAL_CHAT.value,
                "error": True,
                "typing_delay": timing_data["total_delay"],
                "message_complexity": timing_data["complexity"],
                "typing_pattern": timing_data["pattern"],
                "message_chunks": timing_data["chunks"]
            }
    
    async def _analyze_message(self, message: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Analyze message to understand intent, sentiment, and type"""
        
        analysis_prompt = f"""
        Phân tích tin nhắn sau và trả về JSON với các thông tin:
        - type: loại tin nhắn (greeting, question, complaint, purchase_intent, personal_info, followup, goodbye)
        - intent: ý định chính của người dùng
        - sentiment: cảm xúc (positive, negative, neutral)
        - urgency: mức độ khẩn cấp (low, medium, high)
        - entities: các thực thể quan trọng được đề cập
        - requires_human: có cần chuyển cho con người không (true/false)
        
        Tin nhắn: "{message}"
        
        Context: {json.dumps(context or {}, ensure_ascii=False)}
        
        Trả về chỉ JSON, không có text khác:
        """
        
        try:
            response = await self.model.generate_content_async(analysis_prompt)
            analysis = json.loads(response.text.strip())
            
            logger.info("Message analysis completed", analysis=analysis)
            return analysis
            
        except Exception as e:
            logger.warning("Error analyzing message", error=str(e))
            return {
                "type": "question",
                "intent": "general_inquiry",
                "sentiment": "neutral",
                "urgency": "low",
                "entities": [],
                "requires_human": False
            }
    
    async def _route_to_agent(
        self,
        analysis: Dict[str, Any],
        user_id: str,
        conversation_id: str
    ) -> AgentDecision:
        """Route message to appropriate agent based on analysis"""
        
        # Check if human handoff is required
        if analysis.get("requires_human", False) or analysis.get("urgency") == "high":
            return AgentDecision.HANDOFF_HUMAN
        
        # Check conversation state
        conversation = await self.db.get_conversation(conversation_id)
        if conversation and conversation.state == ConversationState.DISCOVERY:
            return AgentDecision.DISCOVERY
        
        # Route based on message type and intent
        message_type = analysis.get("type", "question")
        intent = analysis.get("intent", "")
        
        if message_type == "greeting":
            # Check if user profile is complete
            user_profile = await self.memory_engine.get_user_profile(user_id)
            if not user_profile or len(user_profile.get("personal_info", {})) < 3:
                return AgentDecision.DISCOVERY
            return AgentDecision.GENERAL_CHAT
            
        elif message_type == "complaint":
            return AgentDecision.CUSTOMER_SERVICE
            
        elif message_type == "purchase_intent" or "mua" in intent.lower() or "giá" in intent.lower():
            return AgentDecision.SALES
            
        elif message_type == "personal_info":
            return AgentDecision.DISCOVERY
            
        elif message_type == "followup":
            return AgentDecision.FOLLOWUP
            
        else:
            # Default routing based on conversation history
            recent_messages = await self.db.get_recent_messages(conversation_id, limit=5)
            if recent_messages:
                last_agent = recent_messages[0].metadata.get("agent") if recent_messages[0].metadata else None
                if last_agent == AgentDecision.DISCOVERY.value:
                    return AgentDecision.DISCOVERY
            
            return AgentDecision.GENERAL_CHAT
    
    async def _process_with_agent(
        self,
        agent: AgentDecision,
        message: str,
        user_id: str,
        conversation_id: str,
        memory_context: str,
        rag_context: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process message with specific agent"""
        
        if agent == AgentDecision.DISCOVERY:
            return await self._process_discovery(message, user_id, conversation_id, memory_context, analysis)
        elif agent == AgentDecision.CUSTOMER_SERVICE:
            return await self._process_customer_service(message, memory_context, rag_context, analysis)
        elif agent == AgentDecision.SALES:
            return await self._process_sales(message, memory_context, rag_context, analysis)
        elif agent == AgentDecision.HANDOFF_HUMAN:
            return await self._process_handoff(message, user_id, conversation_id, analysis)
        elif agent == AgentDecision.FOLLOWUP:
            return await self._process_followup(message, user_id, conversation_id, memory_context, analysis)
        else:
            return await self._process_general_chat(message, memory_context, rag_context, analysis)
    
    async def _process_discovery(
        self,
        message: str,
        user_id: str,
        conversation_id: str,
        memory_context: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process with Discovery Agent"""
        
        response = await self.discovery_agent.process_response(
            user_id,
            conversation_id,
            message,
            memory_context
        )
        
        return {
            "response": response["response"],
            "agent": AgentDecision.DISCOVERY.value,
            "next_questions": response.get("next_questions", []),
            "completeness_score": response.get("completeness_score", 0),
            "discovered_info": response.get("discovered_info", {})
        }
    
    async def _process_customer_service(
        self,
        message: str,
        memory_context: str,
        rag_context: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process with Customer Service Agent"""
        
        prompt = self.agent_prompts[AgentDecision.CUSTOMER_SERVICE].format(
            message=message,
            memory_context=memory_context,
            rag_context=rag_context,
            sentiment=analysis.get("sentiment", "neutral"),
            urgency=analysis.get("urgency", "low")
        )
        
        response = await self.model.generate_content_async(prompt)
        
        return {
            "response": response.text.strip(),
            "agent": AgentDecision.CUSTOMER_SERVICE.value,
            "sentiment": analysis.get("sentiment"),
            "resolution_suggested": True
        }
    
    async def _process_sales(
        self,
        message: str,
        memory_context: str,
        rag_context: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process with Sales Agent"""
        
        prompt = self.agent_prompts[AgentDecision.SALES].format(
            message=message,
            memory_context=memory_context,
            rag_context=rag_context,
            intent=analysis.get("intent", ""),
            entities=", ".join(analysis.get("entities", []))
        )
        
        response = await self.model.generate_content_async(prompt)
        
        return {
            "response": response.text.strip(),
            "agent": AgentDecision.SALES.value,
            "sales_opportunity": True,
            "products_mentioned": analysis.get("entities", [])
        }
    
    async def _process_handoff(
        self,
        message: str,
        user_id: str,
        conversation_id: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process handoff to human"""
        
        # Create handoff request
        handoff_request = HandoffRequest(
            user_id=user_id,
            conversation_id=conversation_id,
            reason=analysis.get("intent", "User request"),
            urgency=analysis.get("urgency", "medium"),
            context=json.dumps(analysis),
            status=HandoffStatus.PENDING
        )
        
        await self.db.create_handoff_request(handoff_request)
        
        return {
            "response": "Tôi sẽ chuyển bạn đến với nhân viên hỗ trợ. Vui lòng chờ trong giây lát.",
            "agent": AgentDecision.HANDOFF_HUMAN.value,
            "handoff_requested": True,
            "estimated_wait_time": "2-5 phút"
        }
    
    async def _process_followup(
        self,
        message: str,
        user_id: str,
        conversation_id: str,
        memory_context: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process followup message"""
        
        prompt = self.agent_prompts[AgentDecision.FOLLOWUP].format(
            message=message,
            memory_context=memory_context,
            intent=analysis.get("intent", "")
        )
        
        response = await self.model.generate_content_async(prompt)
        
        return {
            "response": response.text.strip(),
            "agent": AgentDecision.FOLLOWUP.value,
            "followup_completed": True
        }
    
    async def _process_general_chat(
        self,
        message: str,
        memory_context: str,
        rag_context: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process general chat"""
        
        prompt = self.agent_prompts[AgentDecision.GENERAL_CHAT].format(
            message=message,
            memory_context=memory_context,
            rag_context=rag_context,
            sentiment=analysis.get("sentiment", "neutral")
        )
        
        response = await self.model.generate_content_async(prompt)
        
        return {
            "response": response.text.strip(),
            "agent": AgentDecision.GENERAL_CHAT.value,
            "casual_conversation": True
        }
    

    
    def _get_discovery_prompt(self) -> str:
        """Get Discovery Agent prompt"""
        return """
        Bạn là Discovery Agent - chuyên gia thu thập thông tin người dùng một cách tự nhiên và thân thiện.

        Tin nhắn người dùng: {message}
        Thông tin đã biết: {memory_context}

        Hãy:
        1. Trả lời tin nhắn một cách tự nhiên
        2. Khéo léo hỏi thêm thông tin cá nhân (sở thích, công việc, gia đình, sức khỏe)
        3. Tạo không khí thoải mái để người dùng chia sẻ

        Trả lời bằng tiếng Việt, thân thiện và tự nhiên:
        """
    
    def _get_customer_service_prompt(self) -> str:
        """Get Customer Service Agent prompt"""
        return """
        Bạn là Customer Service Agent - chuyên gia hỗ trợ khách hàng chuyên nghiệp.

        Tin nhắn: {message}
        Thông tin khách hàng: {memory_context}
        Kiến thức hỗ trợ: {rag_context}
        Cảm xúc: {sentiment}
        Mức độ khẩn cấp: {urgency}

        Hãy:
        1. Thể hiện sự đồng cảm và hiểu biết
        2. Đưa ra giải pháp cụ thể dựa trên kiến thức
        3. Hỏi thêm thông tin nếu cần thiết
        4. Đảm bảo khách hàng hài lòng

        Trả lời chuyên nghiệp bằng tiếng Việt:
        """
    
    def _get_sales_prompt(self) -> str:
        """Get Sales Agent prompt"""
        return """
        Bạn là Sales Agent - chuyên gia bán hàng thông minh và tư vấn.

        Tin nhắn: {message}
        Thông tin khách hàng: {memory_context}
        Thông tin sản phẩm: {rag_context}
        Ý định: {intent}
        Sản phẩm quan tâm: {entities}

        Hãy:
        1. Hiểu nhu cầu thực sự của khách hàng
        2. Tư vấn sản phẩm phù hợp
        3. Làm nổi bật lợi ích, không chỉ tính năng
        4. Tạo cảm giác cấp thiết nhẹ nhàng
        5. Hướng dẫn bước tiếp theo

        Trả lời thuyết phục bằng tiếng Việt:
        """
    
    def _get_followup_prompt(self) -> str:
        """Get Followup Agent prompt"""
        return """
        Bạn là Followup Agent - chuyên gia theo dõi và chăm sóc khách hàng.

        Tin nhắn: {message}
        Lịch sử tương tác: {memory_context}
        Ý định: {intent}

        Hãy:
        1. Kiểm tra tình hình sau tương tác trước
        2. Đảm bảo khách hàng hài lòng
        3. Đưa ra hỗ trợ bổ sung nếu cần
        4. Tạo mối quan hệ dài hạn

        Trả lời quan tâm bằng tiếng Việt:
        """
    
    def _get_general_chat_prompt(self) -> str:
        """Get General Chat Agent prompt"""
        return """
        Bạn là AI Assistant thân thiện và hữu ích.

        Tin nhắn: {message}
        Thông tin người dùng: {memory_context}
        Kiến thức: {rag_context}
        Cảm xúc: {sentiment}

        Hãy:
        1. Trả lời một cách tự nhiên và thân thiện
        2. Sử dụng thông tin cá nhân để cá nhân hóa
        3. Đưa ra thông tin hữu ích nếu có
        4. Duy trì cuộc trò chuyện tích cực

        Trả lời tự nhiên bằng tiếng Việt:
        """

# Singleton instance
_orchestrator = None

def get_orchestrator() -> Orchestrator:
    """Get orchestrator instance"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator