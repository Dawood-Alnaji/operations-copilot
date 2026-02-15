"""
RAG (Retrieval Augmented Generation) Service for Knowledge Base

Handles document upload, processing, chunking, embedding generation,
and semantic search for internal knowledge retrieval.
"""

import os
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import time

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

# Document processing
try:
    import PyPDF2
    from docx import Document as DocxDocument
    import unstructured
    from unstructured.partition.auto import partition
except ImportError:
    PyPDF2 = None
    DocxDocument = None
    unstructured = None
    partition = None

# Embeddings and vector search
try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
except ImportError:
    SentenceTransformer = None
    faiss = None
    np = None

from knowledge_base.models import Document, DocumentChunk, KnowledgeQuery
from core.tools.basic_llm import basic_llm
from audit.models import AuditLog

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG pipeline operations"""
    
    # Embedding model configuration
    EMBEDDING_MODEL_NAME = getattr(settings, 'EMBEDDING_MODEL', 'all-mpnet-base-v2')
    CHUNK_SIZE = 512  # tokens
    CHUNK_OVERLAP = 50  # tokens
    TOP_K_RESULTS = 5  # number of chunks to retrieve
    
    def __init__(self):
        """Initialize the RAG service with embedding model"""
        if SentenceTransformer is None:
            raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")
        
        self.embedding_model = SentenceTransformer(self.EMBEDDING_MODEL_NAME)
        self.vector_index = None
        self.chunk_id_mapping = {}  # Maps FAISS index to chunk IDs
    
    def upload_document(
        self, 
        file: UploadedFile, 
        title: str, 
        user, 
        metadata: Optional[Dict] = None
    ) -> Tuple[Document, str]:
        """
        Upload and validate a document for processing
        
        Args:
            file: Uploaded file object
            title: Document title
            user: User uploading the document
            metadata: Additional metadata
        
        Returns:
            Tuple of (Document instance, status message)
        """
        try:
            # Calculate file hash for deduplication
            file_hash = self._calculate_file_hash(file)
            
            # Check for duplicate
            existing = Document.objects.filter(file_hash=file_hash).first()
            if existing:
                logger.info(f"Duplicate document detected: {file_hash}")
                return existing, "duplicate"
            
            # Create document record
            doc_metadata = metadata or {}
            doc_metadata['file_size'] = file.size
            doc_metadata['original_name'] = file.name
            
            with transaction.atomic():
                document = Document.objects.create(
                    file=file,
                    title=title,
                    uploaded_by=user,
                    file_hash=file_hash,
                    processing_status='pending',
                    metadata=doc_metadata
                )
                
                # Log upload
                AuditLog.log_action(
                    user=user,
                    action_type='document_upload',
                    resource_type='document',
                    resource_id=document.id,
                    request_payload={'title': title, 'file_size': file.size},
                    success=True
                )
            
            logger.info(f"Document uploaded successfully: {document.id}")
            return document, "uploaded"
        
        except Exception as e:
            logger.error(f"Document upload failed: {e}")
            AuditLog.log_action(
                user=user,
                action_type='document_upload',
                resource_type='document',
                success=False,
                error_message=str(e)
            )
            raise
    
    def process_document(self, document_id: int) -> bool:
        """
        Process document: extract text, chunk, generate embeddings
        
        Args:
            document_id: ID of document to process
        
        Returns:
            True if successful, False otherwise
        """
        try:
            document = Document.objects.get(id=document_id)
            document.processing_status = 'processing'
            document.save()
            
            # Extract text
            logger.info(f"Extracting text from document {document_id}")
            text_pages = self._extract_text(document)
            
            if not text_pages:
                document.processing_status = 'failed'
                document.save()
                return False
            
            # Chunk text
            logger.info(f"Chunking document {document_id}")
            chunks = self._chunk_text(text_pages)
            
            # Generate embeddings and save chunks
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            self._save_chunks_with_embeddings(document, chunks)
            
            # Update document status
            document.processing_status = 'completed'
            document.metadata['total_chunks'] = len(chunks)
            document.metadata['total_pages'] = len(text_pages)
            document.save()
            
            logger.info(f"Document {document_id} processed successfully")
            return True
        
        except Exception as e:
            logger.error(f"Document processing failed for {document_id}: {e}")
            if document:
                document.processing_status = 'failed'
                document.save()
            return False
    
    def query_knowledge(
        self, 
        query_text: str, 
        user, 
        top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Query the knowledge base and generate answer
        
        Args:
            query_text: User's natural language query
            user: User making the query
            top_k: Number of chunks to retrieve (default: TOP_K_RESULTS)
        
        Returns:
            Dict with answer, sources, confidence, etc.
        """
        start_time = time.time()
        top_k = top_k or self.TOP_K_RESULTS
        
        try:
            # Retrieve relevant chunks
            retrieved_chunks = self._retrieve_chunks(query_text, top_k)
            
            if not retrieved_chunks:
                return {
                    'answer': "I couldn't find relevant information in the knowledge base.",
                    'sources': [],
                    'confidence': 0.0
                }
            
            # Generate answer with citations
            answer_data = self._generate_answer(query_text, retrieved_chunks)
            
            # Log query
            response_time_ms = int((time.time() - start_time) * 1000)
            self._log_query(user, query_text, retrieved_chunks, answer_data, response_time_ms)
            
            return answer_data
        
        except Exception as e:
            logger.error(f"Knowledge query failed: {e}")
            raise
    
    def _calculate_file_hash(self, file: UploadedFile) -> str:
        """Calculate SHA-256 hash of file"""
        hasher = hashlib.sha256()
        for chunk in file.chunks():
            hasher.update(chunk)
        file.seek(0)  # Reset file pointer
        return hasher.hexdigest()
    
    def _extract_text(self, document: Document) -> List[Tuple[int, str]]:
        """
        Extract text from PDF or DOCX file
        
        Returns:
            List of (page_number, text) tuples
        """
        file_path = document.file.path
        extension = Path(file_path).suffix.lower()
        
        if unstructured and partition:
            try:
                return self._extract_unstructured(file_path)
            except Exception as e:
                logger.warning(f"Unstructured extraction failed, falling back: {e}")

        if extension == '.pdf':
            return self._extract_pdf(file_path)
        elif extension in ['.docx', '.doc']:
            return self._extract_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")
    
    def _extract_pdf(self, file_path: str) -> List[Tuple[int, str]]:
        """Extract text from PDF"""
        if PyPDF2 is None:
            raise ImportError("PyPDF2 not installed")
        
        pages = []
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page_num, page in enumerate(pdf_reader.pages, start=1):
                text = page.extract_text()
                if text.strip():
                    pages.append((page_num, text))
        
        return pages
    
    def _extract_docx(self, file_path: str) -> List[Tuple[int, str]]:
        """Extract text from DOCX (treat as single page)"""
        if DocxDocument is None:
            raise ImportError("python-docx not installed")
        
        try:
            doc = DocxDocument(file_path)
            full_text = '\n'.join([para.text for para in doc.paragraphs])
            return [(1, full_text)]
        except Exception as e:
            logger.error(f"python-docx failed: {e}")
            if ".doc" in file_path.lower() and "package not found" in str(e).lower():
                raise ValueError("The file appears to be an older .doc format which is not supported by the basic extractor. Please convert to .docx or ensure Unstructured is fully configured.")
            raise

    def _extract_unstructured(self, file_path: str) -> List[Tuple[int, str]]:
        """Extract text using the Unstructured library"""
        elements = partition(filename=file_path)
        
        # Group by page if available, else everything in page 1
        pages_content = {}
        for el in elements:
            page_num = getattr(el.metadata, 'page_number', 1) or 1
            if page_num not in pages_content:
                pages_content[page_num] = []
            pages_content[page_num].append(str(el))
        
        results = []
        for page_num in sorted(pages_content.keys()):
            results.append((page_num, "\n".join(pages_content[page_num])))
        
        return results
    
    def _chunk_text(self, text_pages: List[Tuple[int, str]]) -> List[Dict]:
        """
        Split text into overlapping chunks
        
        Args:
            text_pages: List of (page_number, text) tuples
        
        Returns:
            List of chunk dictionaries with page_number, text, and index
        """
        chunks = []
        chunk_index = 0
        
        for page_num, page_text in text_pages:
            # Simple word-based chunking (approximate token count)
            words = page_text.split()
            
            # Create chunks with overlap
            start = 0
            while start < len(words):
                end = min(start + self.CHUNK_SIZE, len(words))
                chunk_text = ' '.join(words[start:end])
                
                if chunk_text.strip():
                    chunks.append({
                        'page_number': page_num,
                        'text': chunk_text,
                        'index': chunk_index,
                        'metadata': {
                            'word_count': end - start
                        }
                    })
                    chunk_index += 1
                
                # Move to next chunk with overlap
                if end >= len(words):
                    break
                start += self.CHUNK_SIZE - self.CHUNK_OVERLAP
        
        return chunks
    
    def _save_chunks_with_embeddings(self, document: Document, chunks: List[Dict]):
        """Generate embeddings and save chunks to database"""
        with transaction.atomic():
            for chunk_data in chunks:
                # Generate embedding
                embedding = self.embedding_model.encode(chunk_data['text'], convert_to_numpy=True)
                
                # Save chunk
                DocumentChunk.objects.create(
                    document=document,
                    chunk_text=chunk_data['text'],
                    chunk_index=chunk_data['index'],
                    page_number=chunk_data['page_number'],
                    embedding_vector=embedding.tolist(),
                    metadata=chunk_data['metadata']
                )
    
    def _retrieve_chunks(self, query_text: str, top_k: int) -> List[DocumentChunk]:
        """
        Retrieve most relevant chunks using semantic search
        
        Args:
            query_text: User query
            top_k: Number of chunks to retrieve
        
        Returns:
            List of DocumentChunk objects
        """
        # Get all chunks with embeddings
        all_chunks = DocumentChunk.objects.filter(
            embedding_vector__isnull=False,
            document__processing_status='completed'
        ).select_related('document')
        
        if not all_chunks.exists():
            return []
        
        # Build FAISS index
        embeddings = []
        chunk_mapping = {}
        
        for idx, chunk in enumerate(all_chunks):
            if chunk.embedding_vector:
                embeddings.append(chunk.embedding_vector)
                chunk_mapping[idx] = chunk
        
        if not embeddings:
            return []
        
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        # Create FAISS index
        dimension = embeddings_array.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_array)
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query_text, convert_to_numpy=True)
        query_embedding = np.array([query_embedding], dtype=np.float32)
        
        # Search
        distances, indices = index.search(query_embedding, min(top_k, len(embeddings)))
        
        # Retrieve chunks
        retrieved = []
        for idx in indices[0]:
            if idx in chunk_mapping:
                retrieved.append(chunk_mapping[idx])
        
        return retrieved
    
    def _generate_answer(self, query: str, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """Generate answer using LLM with retrieved context"""
        
        # Build context from chunks
        context_parts = []
        sources = []
        
        for chunk in chunks:
            context_parts.append(
                f"[Document: {chunk.document.title}, Page: {chunk.page_number}]\n{chunk.chunk_text}\n"
            )
            sources.append({
                'document': chunk.document.title,
                'page': chunk.page_number,
                'document_id': chunk.document.id
            })
        
        context = "\n---\n".join(context_parts)
        
        # Load prompt template
        from core.utils import render_markdown
        prompt = render_markdown(
            template_name='knowledge_grounded_answer.md',
            context={
                'retrieved_chunks': context,
                'user_query': query
            },
            template_dir='../knowledge_base/prompts'
        )
        
        # Call LLM
        messages = [
            {"role": "system", "content": "You are a knowledgeable assistant for an electricity distribution company."},
            {"role": "user", "content": prompt}
        ]
        
        response = basic_llm.call(messages=messages)
        
        return {
            'answer': response if isinstance(response, str) else response.get('content', ''),
            'sources': sources,
            'confidence': 0.85  # Placeholder - could be calculated from distances
        }
    
    def _log_query(
        self, 
        user, 
        query_text: str, 
        chunks: List[DocumentChunk], 
        answer_data: Dict,
        response_time_ms: int
    ):
        """Log query to database for audit trail"""
        try:
            with transaction.atomic():
                query_log = KnowledgeQuery.objects.create(
                    user=user,
                    query_text=query_text,
                    llm_response=answer_data['answer'],
                    confidence_score=answer_data.get('confidence'),
                    response_time_ms=response_time_ms
                )
                query_log.retrieved_chunks.set(chunks)
                
                # Also log to audit trail
                AuditLog.log_action(
                    user=user,
                    action_type='knowledge_query',
                    resource_type='query',
                    resource_id=query_log.id,
                    request_payload={'query': query_text[:200]},
                    response_summary={'num_sources': len(chunks)},
                    success=True
                )
        except Exception as e:
            logger.error(f"Failed to log query: {e}")
