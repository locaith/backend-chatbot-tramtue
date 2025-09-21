"""
Discovery Agent - Thu thập thông tin user và xây dựng profile
"""
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import structlog

from app.services.memory import get_memory_engine
from app.core.database import get_db
from app.models.database import *

logger = structlog.get_logger()

class DiscoveryAgent:
    """Discovery Agent để thu thập thông tin user"""
    
    def __init__(self):
        self.memory_engine = get_memory_engine()
        self.db = get_db()
        self.logger = logger.bind(component="discovery")
        
        # Discovery questions theo category
        self.discovery_questions = {
            "personal_info": [
                "Chào bạn! Mình có thể gọi bạn là gì ạ?",
                "Bạn bao nhiêu tuổi rồi ạ?",
                "Bạn đang sống ở đâu vậy?"
            ],
            "preferences": [
                "Bạn thường quan tâm đến loại sản phẩm nào nhất?",
                "Ngân sách mà bạn dành cho việc chăm sóc sắc đẹp thường là bao nhiêu?",
                "Bạn có thương hiệu yêu thích nào không?",
                "Bạn thích mua sắm online hay offline hơn?"
            ],
            "health_info": [
                "Bạn có đang mang thai không ạ?",
                "Da của bạn thuộc loại nào? (khô, dầu, hỗn hợp, nhạy cảm)",
                "Bạn có bị dị ứng với thành phần nào không?",
                "Bạn có vấn đề gì về da cần quan tâm đặc biệt không?"
            ],
            "lifestyle": [
                "Bạn có thói quen chăm sóc da hàng ngày như thế nào?",
                "Bạn thường làm việc trong môi trường nào? (văn phòng, ngoài trời...)",
                "Bạn có tập thể thao thường xuyên không?"
            ]
        }
        
        # Information completeness thresholds
        self.completeness_thresholds = {
            "basic": 0.3,      # Có tên, tuổi
            "good": 0.6,       # + preferences cơ bản
            "excellent": 0.8   # + health info, lifestyle
        }
    
    async def analyze_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Phân tích profile user và đưa ra recommendations"""
        try:
            context = await self.memory_engine.get_user_context(user_id)
            
            analysis = {
                "completeness_score": await self._calculate_completeness(context),
                "missing_info": await self._identify_missing_info(context),
                "next_questions": await self._suggest_next_questions(context),
                "profile_summary": await self._generate_profile_summary(context),
                "recommendations": await self._generate_recommendations(context)
            }
            
            self.logger.info("User profile analyzed", 
                           user_id=user_id,
                           completeness=analysis["completeness_score"])
            
            return analysis
            
        except Exception as e:
            self.logger.error("Profile analysis failed", error=str(e))
            return {}
    
    async def process_user_response(self, user_id: str, message: str, conversation_id: str) -> Dict[str, Any]:
        """Xử lý response từ user và extract information"""
        try:
            # Extract memories từ message
            memories = await self.memory_engine.extract_and_store_memories(
                user_id=user_id,
                conversation_text=message,
                source=f"discovery_conversation_{conversation_id}"
            )
            
            # Analyze response quality
            response_analysis = await self._analyze_response_quality(message)
            
            # Get updated profile analysis
            profile_analysis = await self.analyze_user_profile(user_id)
            
            result = {
                "memories_extracted": len(memories),
                "response_quality": response_analysis,
                "profile_completeness": profile_analysis["completeness_score"],
                "next_action": await self._determine_next_action(profile_analysis),
                "extracted_info": [
                    {
                        "key": memory.key,
                        "value": memory.value,
                        "confidence": memory.confidence,
                        "needs_confirmation": memory.needs_confirmation
                    }
                    for memory in memories
                ]
            }
            
            self.logger.info("User response processed", 
                           user_id=user_id,
                           memories_count=len(memories),
                           completeness=profile_analysis["completeness_score"])
            
            return result
            
        except Exception as e:
            self.logger.error("Response processing failed", error=str(e))
            return {}
    
    async def get_discovery_question(self, user_id: str, category: Optional[str] = None) -> Optional[str]:
        """Lấy câu hỏi discovery phù hợp"""
        try:
            context = await self.memory_engine.get_user_context(user_id)
            missing_info = await self._identify_missing_info(context)
            
            if not missing_info:
                return None
            
            # Chọn category ưu tiên
            if category and category in missing_info:
                target_category = category
            else:
                # Ưu tiên theo thứ tự: personal_info -> health_info -> preferences -> lifestyle
                priority_order = ["personal_info", "health_info", "preferences", "lifestyle"]
                target_category = None
                for cat in priority_order:
                    if cat in missing_info:
                        target_category = cat
                        break
            
            if not target_category:
                return None
            
            # Lấy questions cho category
            questions = self.discovery_questions.get(target_category, [])
            if not questions:
                return None
            
            # Chọn question chưa hỏi (simple implementation)
            # TODO: Track asked questions in database
            return questions[0]
            
        except Exception as e:
            self.logger.error("Failed to get discovery question", error=str(e))
            return None
    
    async def should_continue_discovery(self, user_id: str) -> bool:
        """Kiểm tra có nên tiếp tục discovery không"""
        try:
            context = await self.memory_engine.get_user_context(user_id)
            completeness = await self._calculate_completeness(context)
            
            # Continue nếu completeness < good threshold
            return completeness < self.completeness_thresholds["good"]
            
        except Exception as e:
            self.logger.error("Failed to check discovery continuation", error=str(e))
            return False
    
    async def _calculate_completeness(self, context: Dict[str, Any]) -> float:
        """Tính completeness score của user profile"""
        total_weight = 0
        filled_weight = 0
        
        # Weights cho từng category
        category_weights = {
            "personal_info": 0.3,
            "health_info": 0.25,
            "preferences": 0.25,
            "lifestyle": 0.2
        }
        
        for category, weight in category_weights.items():
            total_weight += weight
            category_data = context.get(category, {})
            
            if category == "personal_info":
                # Cần ít nhất name hoặc age
                if "name" in category_data or "age" in category_data:
                    filled_weight += weight * 0.5
                if "name" in category_data and "age" in category_data:
                    filled_weight += weight * 0.5
                    
            elif category == "health_info":
                # Cần skin_type hoặc pregnancy_status
                if "skin_type" in category_data or "pregnancy_status" in category_data:
                    filled_weight += weight * 0.7
                if "allergies" in category_data:
                    filled_weight += weight * 0.3
                    
            elif category == "preferences":
                # Cần ít nhất 1 product preference
                product_prefs = [k for k in category_data.keys() if k.startswith("product_")]
                if product_prefs:
                    filled_weight += weight * 0.6
                if "budget_range" in category_data:
                    filled_weight += weight * 0.4
                    
            elif category == "lifestyle":
                # Bonus points cho lifestyle info
                if category_data:
                    filled_weight += weight * min(len(category_data) * 0.3, 1.0)
        
        return min(filled_weight / total_weight, 1.0) if total_weight > 0 else 0.0
    
    async def _identify_missing_info(self, context: Dict[str, Any]) -> List[str]:
        """Identify missing information categories"""
        missing = []
        
        # Check personal_info
        personal_info = context.get("personal_info", {})
        if not personal_info.get("name") and not personal_info.get("age"):
            missing.append("personal_info")
        
        # Check health_info
        health_info = context.get("health_info", {})
        if not health_info.get("skin_type") and not health_info.get("pregnancy_status"):
            missing.append("health_info")
        
        # Check preferences
        preferences = context.get("preferences", {})
        product_prefs = [k for k in preferences.keys() if k.startswith("product_")]
        if not product_prefs:
            missing.append("preferences")
        
        # Check lifestyle (optional)
        lifestyle = context.get("lifestyle", {})
        if not lifestyle:
            missing.append("lifestyle")
        
        return missing
    
    async def _suggest_next_questions(self, context: Dict[str, Any]) -> List[str]:
        """Suggest next questions based on missing info"""
        missing_info = await self._identify_missing_info(context)
        suggestions = []
        
        for category in missing_info[:2]:  # Top 2 priorities
            questions = self.discovery_questions.get(category, [])
            if questions:
                suggestions.append(questions[0])
        
        return suggestions
    
    async def _generate_profile_summary(self, context: Dict[str, Any]) -> str:
        """Generate a summary of user profile"""
        summary_parts = []
        
        # Personal info
        personal_info = context.get("personal_info", {})
        if personal_info.get("name"):
            summary_parts.append(f"Tên: {personal_info['name']['value']}")
        if personal_info.get("age"):
            summary_parts.append(f"Tuổi: {personal_info['age']['value']}")
        
        # Health info
        health_info = context.get("health_info", {})
        if health_info.get("skin_type"):
            summary_parts.append(f"Loại da: {health_info['skin_type']['value']}")
        if health_info.get("pregnancy_status"):
            summary_parts.append("Đang mang thai")
        
        # Preferences
        preferences = context.get("preferences", {})
        if preferences.get("budget_range"):
            summary_parts.append(f"Ngân sách: {preferences['budget_range']['value']}")
        
        return "; ".join(summary_parts) if summary_parts else "Chưa có thông tin"
    
    async def _generate_recommendations(self, context: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on profile"""
        recommendations = []
        
        health_info = context.get("health_info", {})
        preferences = context.get("preferences", {})
        
        # Skin type based recommendations
        skin_type = health_info.get("skin_type", {}).get("value")
        if skin_type == "dry":
            recommendations.append("Nên sử dụng kem dưỡng ẩm và serum hyaluronic acid")
        elif skin_type == "oily":
            recommendations.append("Nên sử dụng sản phẩm kiểm soát dầu và BHA")
        elif skin_type == "sensitive":
            recommendations.append("Nên chọn sản phẩm không mùi, không cồn")
        
        # Pregnancy recommendations
        if health_info.get("pregnancy_status", {}).get("value"):
            recommendations.append("Tránh retinol, salicylic acid và các thành phần không an toàn cho thai kỳ")
        
        # Budget recommendations
        budget = preferences.get("budget_range", {}).get("value")
        if budget and budget < 500000:
            recommendations.append("Có nhiều sản phẩm chất lượng trong tầm giá của bạn")
        
        return recommendations
    
    async def _analyze_response_quality(self, message: str) -> Dict[str, Any]:
        """Analyze quality of user response"""
        return {
            "length": len(message),
            "has_specific_info": len(re.findall(r'\d+', message)) > 0,
            "engagement_level": "high" if len(message) > 50 else "medium" if len(message) > 20 else "low"
        }
    
    async def _determine_next_action(self, profile_analysis: Dict[str, Any]) -> str:
        """Determine next action based on profile analysis"""
        completeness = profile_analysis.get("completeness_score", 0)
        
        if completeness < self.completeness_thresholds["basic"]:
            return "continue_discovery"
        elif completeness < self.completeness_thresholds["good"]:
            return "targeted_questions"
        elif completeness < self.completeness_thresholds["excellent"]:
            return "optional_discovery"
        else:
            return "ready_for_consultation"

# Global discovery agent instance
_discovery_agent = None

def get_discovery_agent() -> DiscoveryAgent:
    """Get discovery agent instance"""
    global _discovery_agent
    if _discovery_agent is None:
        _discovery_agent = DiscoveryAgent()
    return _discovery_agent