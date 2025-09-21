"""
Human-like Timing Service
Implements realistic typing delays, message splitting, and human-like response patterns
"""
import asyncio
import re
import time
from typing import List, Dict, Any, Tuple
from enum import Enum
import structlog

logger = structlog.get_logger()

class MessageComplexity(Enum):
    """Message complexity levels"""
    SIMPLE = "simple"      # Short, direct responses
    MEDIUM = "medium"      # Normal explanations
    COMPLEX = "complex"    # Long, detailed responses

class TypingPattern(Enum):
    """Different typing patterns"""
    FAST = "fast"          # Quick typer (60-80 WPM)
    NORMAL = "normal"      # Average typer (40-60 WPM)
    SLOW = "slow"          # Slow typer (20-40 WPM)
    THINKING = "thinking"  # Pauses for thinking

class HumanTimingService:
    """Service for human-like timing simulation"""
    
    def __init__(self):
        # Typing speeds (words per minute)
        self.typing_speeds = {
            TypingPattern.FAST: 70,
            TypingPattern.NORMAL: 50,
            TypingPattern.SLOW: 30,
            TypingPattern.THINKING: 25
        }
        
        # Base delays (seconds)
        self.base_delays = {
            MessageComplexity.SIMPLE: 0.5,
            MessageComplexity.MEDIUM: 1.0,
            MessageComplexity.COMPLEX: 2.0
        }
        
        # Sentence endings that indicate natural pauses
        self.pause_indicators = ['.', '!', '?', ':', ';']
        
        # Words that indicate thinking/processing
        self.thinking_words = [
            'hmm', 'well', 'actually', 'let me think', 'you know',
            'basically', 'essentially', 'obviously', 'clearly'
        ]
        
    def calculate_typing_delay(
        self,
        message: str,
        complexity: MessageComplexity = MessageComplexity.MEDIUM,
        pattern: TypingPattern = TypingPattern.NORMAL
    ) -> float:
        """Calculate realistic typing delay for a message"""
        
        # Count words
        word_count = len(message.split())
        
        # Get typing speed
        wpm = self.typing_speeds[pattern]
        
        # Calculate base typing time (words per minute to seconds)
        base_time = (word_count / wpm) * 60
        
        # Add complexity factor
        complexity_factor = {
            MessageComplexity.SIMPLE: 0.8,
            MessageComplexity.MEDIUM: 1.0,
            MessageComplexity.COMPLEX: 1.3
        }
        
        typing_time = base_time * complexity_factor[complexity]
        
        # Add thinking time for complex messages
        thinking_time = self._calculate_thinking_time(message, complexity)
        
        # Add natural pauses
        pause_time = self._calculate_pause_time(message)
        
        total_time = typing_time + thinking_time + pause_time
        
        # Ensure minimum and maximum bounds
        min_time = 0.5
        max_time = 8.0
        
        final_time = max(min_time, min(total_time, max_time))
        
        logger.debug(
            "Calculated typing delay",
            message_length=len(message),
            word_count=word_count,
            complexity=complexity.value,
            pattern=pattern.value,
            typing_time=typing_time,
            thinking_time=thinking_time,
            pause_time=pause_time,
            final_time=final_time
        )
        
        return round(final_time, 1)
    
    def _calculate_thinking_time(self, message: str, complexity: MessageComplexity) -> float:
        """Calculate thinking time based on message content"""
        
        thinking_time = 0.0
        
        # Base thinking time by complexity
        base_thinking = {
            MessageComplexity.SIMPLE: 0.2,
            MessageComplexity.MEDIUM: 0.5,
            MessageComplexity.COMPLEX: 1.0
        }
        
        thinking_time += base_thinking[complexity]
        
        # Add time for thinking words
        message_lower = message.lower()
        for word in self.thinking_words:
            if word in message_lower:
                thinking_time += 0.3
        
        # Add time for questions (requires more thought)
        if '?' in message:
            thinking_time += 0.5
        
        # Add time for numbers/calculations
        if re.search(r'\d+', message):
            thinking_time += 0.3
        
        return thinking_time
    
    def _calculate_pause_time(self, message: str) -> float:
        """Calculate natural pause time based on punctuation"""
        
        pause_time = 0.0
        
        # Count sentence endings
        for indicator in self.pause_indicators:
            count = message.count(indicator)
            if indicator in ['.', '!', '?']:
                pause_time += count * 0.3  # Longer pause for sentence endings
            else:
                pause_time += count * 0.1  # Shorter pause for other punctuation
        
        # Add pause for line breaks
        line_breaks = message.count('\n')
        pause_time += line_breaks * 0.2
        
        return pause_time
    
    def split_long_message(
        self,
        message: str,
        max_length: int = 200,
        preserve_sentences: bool = True
    ) -> List[str]:
        """Split long messages into smaller, natural chunks"""
        
        if len(message) <= max_length:
            return [message]
        
        chunks = []
        
        if preserve_sentences:
            # Split by sentences first
            sentences = re.split(r'([.!?]+)', message)
            current_chunk = ""
            
            for i in range(0, len(sentences), 2):
                if i + 1 < len(sentences):
                    sentence = sentences[i] + sentences[i + 1]
                else:
                    sentence = sentences[i]
                
                if len(current_chunk + sentence) <= max_length:
                    current_chunk += sentence
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = sentence
                    else:
                        # Sentence is too long, split by words
                        word_chunks = self._split_by_words(sentence, max_length)
                        chunks.extend(word_chunks)
            
            if current_chunk:
                chunks.append(current_chunk.strip())
        
        else:
            # Split by words
            chunks = self._split_by_words(message, max_length)
        
        # Clean up chunks
        chunks = [chunk.strip() for chunk in chunks if chunk.strip()]
        
        logger.info(
            "Split message into chunks",
            original_length=len(message),
            chunk_count=len(chunks),
            chunk_lengths=[len(chunk) for chunk in chunks]
        )
        
        return chunks
    
    def _split_by_words(self, text: str, max_length: int) -> List[str]:
        """Split text by words while respecting max length"""
        
        words = text.split()
        chunks = []
        current_chunk = ""
        
        for word in words:
            if len(current_chunk + " " + word) <= max_length:
                if current_chunk:
                    current_chunk += " " + word
                else:
                    current_chunk = word
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = word
                else:
                    # Single word is too long, force split
                    chunks.append(word[:max_length])
                    current_chunk = word[max_length:]
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def determine_complexity(self, message: str) -> MessageComplexity:
        """Automatically determine message complexity"""
        
        word_count = len(message.split())
        sentence_count = len([s for s in re.split(r'[.!?]+', message) if s.strip()])
        
        # Simple heuristics
        if word_count <= 10 and sentence_count <= 1:
            return MessageComplexity.SIMPLE
        elif word_count <= 50 and sentence_count <= 3:
            return MessageComplexity.MEDIUM
        else:
            return MessageComplexity.COMPLEX
    
    def determine_typing_pattern(self, agent_type: str, message_complexity: MessageComplexity) -> TypingPattern:
        """Determine typing pattern based on agent type and message complexity"""
        
        # Different agents have different typing patterns
        agent_patterns = {
            "discovery": TypingPattern.NORMAL,
            "customer_service": TypingPattern.FAST,
            "sales": TypingPattern.FAST,
            "handoff_human": TypingPattern.SLOW,
            "followup": TypingPattern.NORMAL,
            "general_chat": TypingPattern.NORMAL
        }
        
        base_pattern = agent_patterns.get(agent_type, TypingPattern.NORMAL)
        
        # Adjust for complexity
        if message_complexity == MessageComplexity.COMPLEX:
            if base_pattern == TypingPattern.FAST:
                return TypingPattern.NORMAL
            elif base_pattern == TypingPattern.NORMAL:
                return TypingPattern.THINKING
        
        return base_pattern
    
    async def simulate_typing(
        self,
        message: str,
        agent_type: str = "general_chat",
        callback=None
    ) -> Dict[str, Any]:
        """Simulate human-like typing with real-time updates"""
        
        # Determine message properties
        complexity = self.determine_complexity(message)
        pattern = self.determine_typing_pattern(agent_type, complexity)
        
        # Calculate total delay
        total_delay = self.calculate_typing_delay(message, complexity, pattern)
        
        # Split message if too long
        chunks = self.split_long_message(message)
        
        typing_data = {
            "total_delay": total_delay,
            "complexity": complexity.value,
            "pattern": pattern.value,
            "chunks": chunks,
            "chunk_count": len(chunks)
        }
        
        # If callback provided, simulate real-time typing
        if callback:
            await self._simulate_real_time_typing(chunks, total_delay, callback)
        
        return typing_data
    
    async def _simulate_real_time_typing(
        self,
        chunks: List[str],
        total_delay: float,
        callback
    ):
        """Simulate real-time typing with callbacks"""
        
        # Distribute delay across chunks
        chunk_delays = self._distribute_delay(chunks, total_delay)
        
        for i, (chunk, delay) in enumerate(zip(chunks, chunk_delays)):
            # Send typing indicator
            await callback("typing_start", {"chunk_index": i, "total_chunks": len(chunks)})
            
            # Wait for typing delay
            await asyncio.sleep(delay)
            
            # Send chunk
            await callback("chunk_ready", {
                "chunk": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "is_final": i == len(chunks) - 1
            })
        
        # Send completion
        await callback("typing_complete", {"total_time": total_delay})
    
    def _distribute_delay(self, chunks: List[str], total_delay: float) -> List[float]:
        """Distribute total delay across chunks based on their length"""
        
        if not chunks:
            return []
        
        if len(chunks) == 1:
            return [total_delay]
        
        # Calculate weights based on chunk length
        chunk_lengths = [len(chunk) for chunk in chunks]
        total_length = sum(chunk_lengths)
        
        # Distribute delay proportionally
        delays = []
        remaining_delay = total_delay
        
        for i, length in enumerate(chunk_lengths[:-1]):
            weight = length / total_length
            delay = total_delay * weight
            delays.append(delay)
            remaining_delay -= delay
        
        # Last chunk gets remaining delay
        delays.append(max(0.1, remaining_delay))
        
        return delays

# Singleton instance
_timing_service = None

def get_timing_service() -> HumanTimingService:
    """Get timing service instance"""
    global _timing_service
    if _timing_service is None:
        _timing_service = HumanTimingService()
    return _timing_service