"""
Memory Engine service cho user memory management
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import structlog

from app.core.database import get_db
from app.models.database import *

logger = structlog.get_logger()

class MemoryEngine:
    """Memory engine cho short-term và long-term memory"""
    
    def __init__(self):
        self.db = get_db()
        self.logger = logger.bind(component="memory")
        
        # Memory categories và weights
        self.memory_categories = {
            "personal_info": {"weight": 1.0, "confidence_threshold": 0.8},
            "preferences": {"weight": 0.9, "confidence_threshold": 0.7},
            "health_info": {"weight": 1.0, "confidence_threshold": 0.9},
            "purchase_history": {"weight": 0.8, "confidence_threshold": 0.8},
            "communication_style": {"weight": 0.6, "confidence_threshold": 0.6},
            "context": {"weight": 0.5, "confidence_threshold": 0.5}
        }
    
    async def extract_and_store_memories(self, user_id: str, conversation_text: str, source: str = "conversation") -> List[Memory]:
        """Extract memories từ conversation text"""
        self.logger.info("Extracting memories", user_id=user_id, source=source)
        
        try:
            memories_extracted = []
            
            # Extract different types of information
            personal_info = await self._extract_personal_info(conversation_text)
            preferences = await self._extract_preferences(conversation_text)
            health_info = await self._extract_health_info(conversation_text)
            
            # Store personal info memories
            for key, value in personal_info.items():
                memory = await self._store_memory(
                    user_id=user_id,
                    key=f"personal_info.{key}",
                    value=value["value"],
                    confidence=value["confidence"],
                    source=source,
                    category="personal_info"
                )
                if memory:
                    memories_extracted.append(memory)
            
            # Store preferences memories
            for key, value in preferences.items():
                memory = await self._store_memory(
                    user_id=user_id,
                    key=f"preferences.{key}",
                    value=value["value"],
                    confidence=value["confidence"],
                    source=source,
                    category="preferences"
                )
                if memory:
                    memories_extracted.append(memory)
            
            # Store health info memories
            for key, value in health_info.items():
                memory = await self._store_memory(
                    user_id=user_id,
                    key=f"health_info.{key}",
                    value=value["value"],
                    confidence=value["confidence"],
                    source=source,
                    category="health_info",
                    needs_confirmation=True  # Health info cần confirmation
                )
                if memory:
                    memories_extracted.append(memory)
            
            self.logger.info("Memories extracted", 
                           user_id=user_id, 
                           count=len(memories_extracted))
            
            return memories_extracted
            
        except Exception as e:
            self.logger.error("Memory extraction failed", error=str(e))
            return []
    
    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Lấy user context từ memories"""
        try:
            memories = await self.db.get_user_memories(user_id)
            
            context = {
                "personal_info": {},
                "preferences": {},
                "health_info": {},
                "purchase_history": {},
                "communication_style": {},
                "context": {}
            }
            
            for memory in memories:
                # Parse memory key
                parts = memory.key.split(".", 1)
                if len(parts) == 2:
                    category, key = parts
                    if category in context:
                        context[category][key] = {
                            "value": memory.value,
                            "confidence": memory.confidence,
                            "weight": memory.weight,
                            "needs_confirmation": memory.needs_confirmation,
                            "updated_at": memory.updated_at
                        }
            
            self.logger.info("User context retrieved", 
                           user_id=user_id,
                           categories=list(context.keys()))
            
            return context
            
        except Exception as e:
            self.logger.error("Failed to get user context", error=str(e))
            return {}
    
    async def update_memory(self, user_id: str, key: str, value: Any, confidence: float, source: str = "update") -> Optional[Memory]:
        """Update existing memory hoặc tạo mới"""
        try:
            # Tìm existing memory
            memories = await self.db.get_user_memories(user_id)
            existing_memory = next((m for m in memories if m.key == key), None)
            
            if existing_memory:
                # Update existing memory với confidence weighting
                new_confidence = (existing_memory.confidence + confidence) / 2
                new_weight = min(existing_memory.weight + 0.1, 1.0)  # Increase weight
                
                updated_memory = await self.db.update_memory(
                    existing_memory.id,
                    {
                        "value": value,
                        "confidence": new_confidence,
                        "weight": new_weight,
                        "source": source
                    }
                )
                
                self.logger.info("Memory updated", 
                               user_id=user_id, 
                               key=key,
                               confidence=new_confidence)
                
                return updated_memory
            else:
                # Create new memory
                return await self._store_memory(user_id, key, value, confidence, source)
                
        except Exception as e:
            self.logger.error("Failed to update memory", error=str(e))
            return None
    
    async def confirm_memory(self, user_id: str, key: str) -> Optional[Memory]:
        """Confirm a memory that needs confirmation"""
        try:
            memories = await self.db.get_user_memories(user_id)
            memory = next((m for m in memories if m.key == key), None)
            
            if memory and memory.needs_confirmation:
                updated_memory = await self.db.update_memory(
                    memory.id,
                    {
                        "needs_confirmation": False,
                        "confirmed_at": datetime.utcnow(),
                        "confidence": min(memory.confidence + 0.2, 1.0),
                        "weight": min(memory.weight + 0.2, 1.0)
                    }
                )
                
                self.logger.info("Memory confirmed", user_id=user_id, key=key)
                return updated_memory
            
            return memory
            
        except Exception as e:
            self.logger.error("Failed to confirm memory", error=str(e))
            return None
    
    async def _store_memory(self, user_id: str, key: str, value: Any, confidence: float, source: str, category: str = "context", needs_confirmation: bool = False) -> Optional[Memory]:
        """Store memory với validation"""
        try:
            # Get category config
            category_config = self.memory_categories.get(category, {"weight": 0.5, "confidence_threshold": 0.5})
            
            # Check confidence threshold
            if confidence < category_config["confidence_threshold"]:
                self.logger.debug("Memory confidence too low", 
                                key=key, 
                                confidence=confidence,
                                threshold=category_config["confidence_threshold"])
                return None
            
            memory_data = MemoryCreate(
                user_id=user_id,
                key=key,
                value=value,
                confidence=confidence,
                weight=category_config["weight"],
                source=source,
                needs_confirmation=needs_confirmation
            )
            
            memory = await self.db.create_memory(memory_data)
            
            self.logger.info("Memory stored", 
                           user_id=user_id, 
                           key=key,
                           confidence=confidence)
            
            return memory
            
        except Exception as e:
            self.logger.error("Failed to store memory", error=str(e))
            return None
    
    async def _extract_personal_info(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Extract personal information từ text"""
        personal_info = {}
        
        # Name extraction
        name_patterns = [
            r"tên (?:tôi là|của tôi là|mình là) ([A-Za-zÀ-ỹ\s]+)",
            r"mình là ([A-Za-zÀ-ỹ\s]+)",
            r"tôi là ([A-Za-zÀ-ỹ\s]+)",
            r"em tên ([A-Za-zÀ-ỹ\s]+)"
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 1 and len(name) < 50:
                    personal_info["name"] = {
                        "value": name,
                        "confidence": 0.9
                    }
                    break
        
        # Age extraction
        age_patterns = [
            r"(?:tuổi|năm nay) (\d{1,2})",
            r"(\d{1,2}) tuổi",
            r"sinh năm (\d{4})"
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                age_value = match.group(1)
                if pattern.endswith(r"(\d{4})"):  # Birth year
                    current_year = datetime.now().year
                    age = current_year - int(age_value)
                    if 10 <= age <= 100:
                        personal_info["age"] = {
                            "value": age,
                            "confidence": 0.8
                        }
                else:  # Direct age
                    age = int(age_value)
                    if 10 <= age <= 100:
                        personal_info["age"] = {
                            "value": age,
                            "confidence": 0.9
                        }
                break
        
        # Phone extraction
        phone_patterns = [
            r"(?:số điện thoại|sdt|phone) (?:là )?(\d{10,11})",
            r"(\d{10,11})",  # Simple phone number
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) in [10, 11] and match.startswith(('0', '84')):
                    personal_info["phone"] = {
                        "value": match,
                        "confidence": 0.8
                    }
                    break
        
        return personal_info
    
    async def _extract_preferences(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Extract preferences từ text"""
        preferences = {}
        
        # Product preferences
        product_keywords = {
            "skincare": ["kem dưỡng", "serum", "toner", "cleanser", "chăm sóc da"],
            "makeup": ["son", "phấn", "mascara", "foundation", "trang điểm"],
            "haircare": ["dầu gội", "dầu xả", "chăm sóc tóc"],
            "fragrance": ["nước hoa", "perfume"]
        }
        
        for category, keywords in product_keywords.items():
            for keyword in keywords:
                if keyword in text.lower():
                    preferences[f"product_{category}"] = {
                        "value": True,
                        "confidence": 0.7
                    }
        
        # Budget preferences
        budget_patterns = [
            r"ngân sách (?:khoảng |)(\d+)",
            r"(\d+)k?(?:\s*đồng|\s*vnđ|\s*vnd)",
            r"dưới (\d+)"
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                budget = int(match.group(1))
                if budget > 1000:  # Reasonable budget
                    preferences["budget_range"] = {
                        "value": budget,
                        "confidence": 0.8
                    }
                    break
        
        return preferences
    
    async def _extract_health_info(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Extract health information từ text"""
        health_info = {}
        
        # Pregnancy detection
        pregnancy_keywords = ["có thai", "mang thai", "bầu bí", "thai kỳ", "em bé"]
        if any(keyword in text.lower() for keyword in pregnancy_keywords):
            health_info["pregnancy_status"] = {
                "value": True,
                "confidence": 0.9
            }
        
        # Allergy detection
        allergy_patterns = [
            r"dị ứng (?:với )?([A-Za-zÀ-ỹ\s]+)",
            r"bị dị ứng ([A-Za-zÀ-ỹ\s]+)",
            r"không dùng được ([A-Za-zÀ-ỹ\s]+)"
        ]
        
        allergies = []
        for pattern in allergy_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            allergies.extend([match.strip() for match in matches])
        
        if allergies:
            health_info["allergies"] = {
                "value": allergies,
                "confidence": 0.9
            }
        
        # Skin type detection
        skin_types = {
            "da khô": "dry",
            "da dầu": "oily", 
            "da hỗn hợp": "combination",
            "da nhạy cảm": "sensitive",
            "da thường": "normal"
        }
        
        for vietnamese, english in skin_types.items():
            if vietnamese in text.lower():
                health_info["skin_type"] = {
                    "value": english,
                    "confidence": 0.8
                }
                break
        
        return health_info

# Global memory engine instance
_memory_engine = None

def get_memory_engine() -> MemoryEngine:
    """Get memory engine instance"""
    global _memory_engine
    if _memory_engine is None:
        _memory_engine = MemoryEngine()
    return _memory_engine