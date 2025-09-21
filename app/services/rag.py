"""
RAG (Retrieval-Augmented Generation) service
"""
import asyncio
import hashlib
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
import aiohttp
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import structlog

from app.core.config import get_config
from app.core.database import get_db
from app.models.database import *

logger = structlog.get_logger()

class RAGService:
    """RAG service cho document ingestion và search"""
    
    def __init__(self):
        self.config = get_config()
        self.db = get_db()
        self.logger = logger.bind(component="rag")
        
        # Load embedding model
        self.embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.embedding_dimension = 384
        
        # Load RAG config
        self.rag_config = self.config.get_rag_config()
        
    async def ingest_website(self, url: str, max_pages: int = 10) -> Dict[str, Any]:
        """Ingest website content"""
        self.logger.info("Starting website ingestion", url=url, max_pages=max_pages)
        
        try:
            visited_urls = set()
            to_visit = [url]
            documents_created = 0
            chunks_created = 0
            
            async with aiohttp.ClientSession() as session:
                while to_visit and len(visited_urls) < max_pages:
                    current_url = to_visit.pop(0)
                    if current_url in visited_urls:
                        continue
                    
                    visited_urls.add(current_url)
                    
                    try:
                        # Fetch page content
                        async with session.get(current_url, timeout=30) as response:
                            if response.status != 200:
                                continue
                            
                            content = await response.text()
                            
                        # Parse content
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # Remove script and style elements
                        for script in soup(["script", "style"]):
                            script.decompose()
                        
                        # Extract text
                        text = soup.get_text()
                        text = re.sub(r'\s+', ' ', text).strip()
                        
                        if len(text) < 100:  # Skip pages with too little content
                            continue
                        
                        # Extract title
                        title_tag = soup.find('title')
                        title = title_tag.get_text().strip() if title_tag else current_url
                        
                        # Create document
                        content_hash = hashlib.sha256(text.encode()).hexdigest()
                        
                        # Check if document already exists
                        existing_doc = await self.db.get_document_by_hash(content_hash)
                        if existing_doc:
                            self.logger.info("Document already exists", url=current_url)
                            continue
                        
                        # Create document
                        doc_data = DocumentCreate(
                            source_type="website",
                            source_url=current_url,
                            title=title,
                            content_hash=content_hash,
                            metadata={"scraped_at": datetime.utcnow().isoformat()}
                        )
                        document = await self.db.create_document(doc_data)
                        documents_created += 1
                        
                        # Chunk and embed document
                        chunks = await self._chunk_text(text)
                        for i, chunk in enumerate(chunks):
                            # Create chunk
                            chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()
                            chunk_data = DocChunkCreate(
                                document_id=document.id,
                                chunk_index=i,
                                content=chunk,
                                content_hash=chunk_hash
                            )
                            doc_chunk = await self.db.create_doc_chunk(chunk_data)
                            
                            # Create embedding
                            embedding = self.embedding_model.encode(chunk).tolist()
                            embedding_data = DocEmbeddingCreate(
                                chunk_id=doc_chunk.id,
                                embedding=embedding,
                                model_name="sentence-transformers/all-MiniLM-L6-v2",
                                dimension=self.embedding_dimension
                            )
                            await self.db.create_doc_embedding(embedding_data)
                            chunks_created += 1
                        
                        # Update document total chunks
                        await self.db.update_document(document.id, {"total_chunks": len(chunks)})
                        
                        # Find more URLs to visit
                        if len(visited_urls) < max_pages:
                            base_domain = urlparse(url).netloc
                            for link in soup.find_all('a', href=True):
                                href = link['href']
                                full_url = urljoin(current_url, href)
                                parsed_url = urlparse(full_url)
                                
                                # Only follow links on same domain
                                if (parsed_url.netloc == base_domain and 
                                    full_url not in visited_urls and 
                                    full_url not in to_visit):
                                    to_visit.append(full_url)
                        
                        self.logger.info("Page processed", 
                                       url=current_url, 
                                       chunks=len(chunks))
                        
                    except Exception as e:
                        self.logger.error("Failed to process page", 
                                        url=current_url, error=str(e))
                        continue
            
            result = {
                "status": "success",
                "documents_created": documents_created,
                "chunks_created": chunks_created,
                "pages_visited": len(visited_urls)
            }
            
            self.logger.info("Website ingestion completed", **result)
            return result
            
        except Exception as e:
            self.logger.error("Website ingestion failed", error=str(e))
            raise
    
    async def ingest_file(self, file_path: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Ingest file content"""
        self.logger.info("Starting file ingestion", file_path=file_path)
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if len(content) < 100:
                raise ValueError("File content too short")
            
            # Create document
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Check if document already exists
            existing_doc = await self.db.get_document_by_hash(content_hash)
            if existing_doc:
                return {
                    "status": "exists",
                    "document_id": existing_doc.id,
                    "message": "Document already exists"
                }
            
            doc_title = title or file_path.split('/')[-1]
            doc_data = DocumentCreate(
                source_type="file",
                source_path=file_path,
                title=doc_title,
                content_hash=content_hash,
                metadata={"ingested_at": datetime.utcnow().isoformat()}
            )
            document = await self.db.create_document(doc_data)
            
            # Chunk and embed document
            chunks = await self._chunk_text(content)
            chunks_created = 0
            
            for i, chunk in enumerate(chunks):
                # Create chunk
                chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()
                chunk_data = DocChunkCreate(
                    document_id=document.id,
                    chunk_index=i,
                    content=chunk,
                    content_hash=chunk_hash
                )
                doc_chunk = await self.db.create_doc_chunk(chunk_data)
                
                # Create embedding
                embedding = self.embedding_model.encode(chunk).tolist()
                embedding_data = DocEmbeddingCreate(
                    chunk_id=doc_chunk.id,
                    embedding=embedding,
                    model_name="sentence-transformers/all-MiniLM-L6-v2",
                    dimension=self.embedding_dimension
                )
                await self.db.create_doc_embedding(embedding_data)
                chunks_created += 1
            
            # Update document total chunks
            await self.db.update_document(document.id, {"total_chunks": len(chunks)})
            
            result = {
                "status": "success",
                "document_id": document.id,
                "chunks_created": chunks_created
            }
            
            self.logger.info("File ingestion completed", **result)
            return result
            
        except Exception as e:
            self.logger.error("File ingestion failed", error=str(e))
            raise
    
    async def search(self, query: str, top_k: int = 5, threshold: float = 0.7) -> List[RAGSearchResult]:
        """Search documents using vector similarity"""
        self.logger.info("Starting RAG search", query=query[:100], top_k=top_k)
        
        try:
            # Create query embedding
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Perform vector search
            search_results = await self.db.vector_search(
                query_embedding=query_embedding,
                top_k=top_k,
                threshold=threshold
            )
            
            # Convert to response format
            results = []
            for row in search_results:
                result = RAGSearchResult(
                    chunk_id=row['chunk_id'],
                    content=row['content'],
                    score=row['similarity'],
                    document_title=row['title'],
                    source_url=row.get('source_url'),
                    metadata=row.get('metadata', {})
                )
                results.append(result)
            
            self.logger.info("RAG search completed", 
                           results_count=len(results),
                           top_score=results[0].score if results else 0)
            
            return results
            
        except Exception as e:
            self.logger.error("RAG search failed", error=str(e))
            raise
    
    async def _chunk_text(self, text: str) -> List[str]:
        """Chunk text into smaller pieces"""
        chunk_size = self.rag_config.get("chunk_size", 500)
        chunk_overlap = self.rag_config.get("chunk_overlap", 50)
        
        # Simple sentence-based chunking
        sentences = re.split(r'[.!?]+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                
                # Start new chunk with overlap
                if chunk_overlap > 0:
                    words = current_chunk.split()
                    overlap_words = words[-chunk_overlap:] if len(words) > chunk_overlap else words
                    current_chunk = " ".join(overlap_words) + " " + sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # Filter out very short chunks
        chunks = [chunk for chunk in chunks if len(chunk) > 50]
        
        return chunks
    
    async def get_context_for_query(self, query: str, max_context_length: int = 2000) -> str:
        """Get relevant context for a query"""
        try:
            search_results = await self.search(query, top_k=5, threshold=0.6)
            
            if not search_results:
                return ""
            
            # Combine results into context
            context_parts = []
            current_length = 0
            
            for result in search_results:
                content = result.content
                if current_length + len(content) > max_context_length:
                    # Truncate to fit
                    remaining_space = max_context_length - current_length
                    if remaining_space > 100:  # Only add if meaningful space left
                        content = content[:remaining_space] + "..."
                        context_parts.append(f"[Score: {result.score:.2f}] {content}")
                    break
                
                context_parts.append(f"[Score: {result.score:.2f}] {content}")
                current_length += len(content)
            
            context = "\n\n".join(context_parts)
            
            self.logger.info("Context generated", 
                           context_length=len(context),
                           sources_used=len(context_parts))
            
            return context
            
        except Exception as e:
            self.logger.error("Failed to get context", error=str(e))
            return ""

# Global RAG service instance
_rag_service = None

def get_rag_service() -> RAGService:
    """Get RAG service instance"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service