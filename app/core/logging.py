"""
Logging configuration với structlog
"""
import sys
import uuid
import structlog
from typing import Any, Dict
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger

# Context variable để lưu correlation ID
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')

def setup_logging():
    """Setup structlog configuration"""
    
    # Processors cho structlog
    processors = [
        # Add correlation ID to all log entries
        add_correlation_id,
        # Add timestamp
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        # JSON formatting
        structlog.processors.JSONRenderer()
    ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    import logging
    
    # Create JSON formatter
    json_formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    
    # Setup handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(json_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

def add_correlation_id(logger, method_name, event_dict):
    """Add correlation ID to log entries"""
    correlation_id = correlation_id_var.get()
    if correlation_id:
        event_dict['correlation_id'] = correlation_id
    return event_dict

def set_correlation_id(correlation_id: str = None) -> str:
    """Set correlation ID for current context"""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id

def get_correlation_id() -> str:
    """Get current correlation ID"""
    return correlation_id_var.get()

def get_logger(name: str = None):
    """Get structured logger"""
    return structlog.get_logger(name)

class LoggingMiddleware:
    """Middleware để log requests và set correlation ID"""
    
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Set correlation ID cho request
            correlation_id = set_correlation_id()
            
            # Log request start
            logger = get_logger("request")
            logger.info(
                "Request started",
                method=scope["method"],
                path=scope["path"],
                correlation_id=correlation_id
            )
            
            # Wrap send để log response
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    logger.info(
                        "Request completed",
                        status_code=message["status"],
                        correlation_id=correlation_id
                    )
                await send(message)
                
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)

class RequestLogger:
    """Helper class để log API calls và metrics"""
    
    def __init__(self):
        self.logger = get_logger("api")
        
    def log_chat_request(self, user_id: str, message_length: int, 
                        agent_type: str = None, model: str = None):
        """Log chat request"""
        self.logger.info(
            "Chat request",
            user_id=user_id,
            message_length=message_length,
            agent_type=agent_type,
            model=model
        )
        
    def log_chat_response(self, user_id: str, response_length: int,
                         processing_time: float, tokens_used: int = None,
                         used_rag: bool = False, used_serper: bool = False):
        """Log chat response"""
        self.logger.info(
            "Chat response",
            user_id=user_id,
            response_length=response_length,
            processing_time_ms=processing_time * 1000,
            tokens_used=tokens_used,
            used_rag=used_rag,
            used_serper=used_serper
        )
        
    def log_rag_operation(self, operation: str, chunks_processed: int = None,
                         processing_time: float = None, success: bool = True):
        """Log RAG operations"""
        self.logger.info(
            "RAG operation",
            operation=operation,
            chunks_processed=chunks_processed,
            processing_time_ms=processing_time * 1000 if processing_time else None,
            success=success
        )
        
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """Log errors với context"""
        self.logger.error(
            "Error occurred",
            error_type=type(error).__name__,
            error_message=str(error),
            context=context or {}
        )
        
    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log security events"""
        self.logger.warning(
            "Security event",
            event_type=event_type,
            details=details
        )

# Global request logger instance
request_logger = RequestLogger()

def get_request_logger() -> RequestLogger:
    """Get global request logger"""
    return request_logger