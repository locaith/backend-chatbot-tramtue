"""
RAG API endpoints
"""
import time
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
import structlog

from app.services.rag import get_rag_service
from app.models.database import RAGSearchRequest, RAGSearchResponse, RAGSearchResult
from app.core.logging import RequestLogger

logger = structlog.get_logger()
router = APIRouter(prefix="/rag", tags=["RAG"])

# Request models
class IngestWebsiteRequest(BaseModel):
    """Website ingestion request"""
    url: str = Field(..., description="Website URL to ingest")
    max_pages: int = Field(default=10, ge=1, le=50, description="Maximum pages to crawl")

class IngestFileRequest(BaseModel):
    """File ingestion request"""
    file_path: str = Field(..., description="Path to file to ingest")
    title: str = Field(None, description="Optional title for the document")

class IngestResponse(BaseModel):
    """Ingestion response"""
    status: str
    message: str
    documents_created: int = 0
    chunks_created: int = 0
    pages_visited: int = 0
    document_id: str = None

@router.post("/ingest/website", response_model=IngestResponse)
async def ingest_website(
    request: IngestWebsiteRequest,
    background_tasks: BackgroundTasks,
    request_logger: RequestLogger = Depends()
):
    """
    Ingest website content for RAG
    
    This endpoint crawls a website and ingests its content into the vector database.
    The process runs in the background for better performance.
    """
    start_time = time.time()
    
    try:
        request_logger.log_request("rag_ingest_website", {
            "url": request.url,
            "max_pages": request.max_pages
        })
        
        rag_service = get_rag_service()
        
        # Run ingestion in background for better UX
        def run_ingestion():
            try:
                result = asyncio.run(rag_service.ingest_website(
                    url=request.url,
                    max_pages=request.max_pages
                ))
                logger.info("Website ingestion completed in background", **result)
            except Exception as e:
                logger.error("Background website ingestion failed", error=str(e))
        
        background_tasks.add_task(run_ingestion)
        
        processing_time = (time.time() - start_time) * 1000
        
        response = IngestResponse(
            status="accepted",
            message=f"Website ingestion started for {request.url}. Processing in background.",
            documents_created=0,
            chunks_created=0,
            pages_visited=0
        )
        
        request_logger.log_response("rag_ingest_website", response.model_dump(), processing_time)
        
        return response
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        error_msg = f"Failed to start website ingestion: {str(e)}"
        
        request_logger.log_error("rag_ingest_website", error_msg, processing_time)
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    request: IngestFileRequest,
    request_logger: RequestLogger = Depends()
):
    """
    Ingest file content for RAG
    
    This endpoint ingests a file's content into the vector database.
    """
    start_time = time.time()
    
    try:
        request_logger.log_request("rag_ingest_file", {
            "file_path": request.file_path,
            "title": request.title
        })
        
        rag_service = get_rag_service()
        
        result = await rag_service.ingest_file(
            file_path=request.file_path,
            title=request.title
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        response = IngestResponse(
            status=result["status"],
            message=f"File ingestion completed: {result.get('message', 'Success')}",
            documents_created=1 if result["status"] == "success" else 0,
            chunks_created=result.get("chunks_created", 0),
            document_id=result.get("document_id")
        )
        
        request_logger.log_response("rag_ingest_file", response.model_dump(), processing_time)
        
        return response
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        error_msg = f"Failed to ingest file: {str(e)}"
        
        request_logger.log_error("rag_ingest_file", error_msg, processing_time)
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/search", response_model=RAGSearchResponse)
async def search_documents(
    request: RAGSearchRequest,
    request_logger: RequestLogger = Depends()
):
    """
    Search documents using vector similarity
    
    This endpoint performs semantic search across ingested documents
    and returns the most relevant chunks.
    """
    start_time = time.time()
    
    try:
        request_logger.log_request("rag_search", {
            "query": request.query[:100],  # Log first 100 chars
            "top_k": request.top_k,
            "threshold": request.threshold
        })
        
        rag_service = get_rag_service()
        
        search_results = await rag_service.search(
            query=request.query,
            top_k=request.top_k,
            threshold=request.threshold
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        response = RAGSearchResponse(
            results=search_results,
            total_found=len(search_results),
            query_time_ms=processing_time
        )
        
        request_logger.log_response("rag_search", {
            "results_count": len(search_results),
            "top_score": search_results[0].score if search_results else 0
        }, processing_time)
        
        return response
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        error_msg = f"Search failed: {str(e)}"
        
        request_logger.log_error("rag_search", error_msg, processing_time)
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/context/{query}")
async def get_context(
    query: str,
    max_length: int = 2000,
    request_logger: RequestLogger = Depends()
):
    """
    Get relevant context for a query
    
    This endpoint returns formatted context that can be used
    directly in chat completions.
    """
    start_time = time.time()
    
    try:
        request_logger.log_request("rag_context", {
            "query": query[:100],
            "max_length": max_length
        })
        
        rag_service = get_rag_service()
        
        context = await rag_service.get_context_for_query(
            query=query,
            max_context_length=max_length
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        response = {
            "context": context,
            "context_length": len(context),
            "query_time_ms": processing_time
        }
        
        request_logger.log_response("rag_context", {
            "context_length": len(context)
        }, processing_time)
        
        return response
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        error_msg = f"Context retrieval failed: {str(e)}"
        
        request_logger.log_error("rag_context", error_msg, processing_time)
        
        raise HTTPException(status_code=500, detail=error_msg)

@router.get("/stats")
async def get_rag_stats(request_logger: RequestLogger = Depends()):
    """
    Get RAG system statistics
    
    Returns statistics about ingested documents and search performance.
    """
    start_time = time.time()
    
    try:
        request_logger.log_request("rag_stats", {})
        
        # This would typically query the database for stats
        # For now, return placeholder stats
        stats = {
            "total_documents": 0,
            "total_chunks": 0,
            "total_embeddings": 0,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "embedding_dimension": 384
        }
        
        processing_time = (time.time() - start_time) * 1000
        
        request_logger.log_response("rag_stats", stats, processing_time)
        
        return stats
        
    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        error_msg = f"Failed to get RAG stats: {str(e)}"
        
        request_logger.log_error("rag_stats", error_msg, processing_time)
        
        raise HTTPException(status_code=500, detail=error_msg)