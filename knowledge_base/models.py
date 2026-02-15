from django.db import models
from django.contrib.auth.models import User
from django.core.validators import FileExtensionValidator
import hashlib


class Document(models.Model):
    """Uploaded internal documents (PDF, DOCX) for RAG knowledge base"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    file = models.FileField(
        upload_to='documents/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'doc'])]
    )
    title = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_documents')
    upload_timestamp = models.DateTimeField(auto_now_add=True)
    file_hash = models.CharField(max_length=64, unique=True, help_text="SHA-256 hash for deduplication")
    processing_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional metadata (file size, pages, etc.)")
    
    class Meta:
        ordering = ['-upload_timestamp']
        indexes = [
            models.Index(fields=['file_hash']),
            models.Index(fields=['processing_status']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.processing_status})"
    
    def clean(self):
        """Validate that the document content is unique"""
        from django.core.exceptions import ValidationError
        
        if self.file and not self.file_hash:
            # Calculate hash for validation
            hasher = hashlib.sha256()
            for chunk in self.file.chunks():
                hasher.update(chunk)
            self.file_hash = hasher.hexdigest()
            # Reset file pointer for subsequent reads
            self.file.seek(0)
            
        # Check for duplicates excluding this instance
        existing = Document.objects.filter(file_hash=self.file_hash)
        if self.pk:
            existing = existing.exclude(pk=self.pk)
            
        if existing.exists():
            raise ValidationError({
                'file': f"This document has already been uploaded as '{existing.first().title}'."
            })

    def save(self, *args, **kwargs):
        """Generate file hash on save if not already set and run validation"""
        if not self.file_hash and self.file:
            # Re-run clean to ensure hash is set and unique
            self.clean()
        super().save(*args, **kwargs)


class DocumentChunk(models.Model):
    """Chunked text segments with embeddings from processed documents"""
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_text = models.TextField(help_text="Extracted text chunk")
    chunk_index = models.IntegerField(help_text="Sequential position in document")
    page_number = models.IntegerField(null=True, blank=True, help_text="Source page number")
    embedding_vector = models.JSONField(
        null=True, 
        blank=True, 
        help_text="Vector embedding for semantic search (stored as list)"
    )
    metadata = models.JSONField(
        default=dict, 
        blank=True, 
        help_text="Additional chunk metadata (char position, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['document', 'chunk_index']
        indexes = [
            models.Index(fields=['document', 'chunk_index']),
            models.Index(fields=['page_number']),
        ]
        unique_together = [['document', 'chunk_index']]
    
    def __str__(self):
        return f"Chunk {self.chunk_index} from {self.document.title} (Page {self.page_number})"


class KnowledgeQuery(models.Model):
    """Log of user queries with retrieved context and LLM responses"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='knowledge_queries')
    query_text = models.TextField(help_text="User's natural language query")
    retrieved_chunks = models.ManyToManyField(
        DocumentChunk, 
        related_name='queries', 
        help_text="Chunks retrieved via vector search"
    )
    llm_response = models.TextField(help_text="Generated answer from LLM")
    confidence_score = models.FloatField(
        null=True, 
        blank=True, 
        help_text="Confidence score (0.0-1.0)"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    feedback_rating = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="User feedback rating (1-5 stars)"
    )
    response_time_ms = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Response time in milliseconds"
    )
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]
    
    def __str__(self):
        return f"Query by {self.user.username} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
