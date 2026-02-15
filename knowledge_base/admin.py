from django.contrib import admin
from knowledge_base.models import Document, DocumentChunk, KnowledgeQuery

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'uploaded_by', 'upload_timestamp', 'processing_status']
    list_filter = ['processing_status', 'upload_timestamp']
    search_fields = ['title', 'uploaded_by__username']
    readonly_fields = ['file_hash', 'upload_timestamp']
    
    def save_model(self, request, obj, form, change):
        """Trigger RAG processing when document is saved"""
        super().save_model(request, obj, form, change)
        
        # Only trigger processing for new documents or if explicitly requested
        if not change or obj.processing_status == 'pending':
            from knowledge_base.services.rag_service import RAGService
            import threading
            
            def run_processing():
                try:
                    rag_service = RAGService()
                    rag_service.process_document(obj.id)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Async processing failed: {e}")
            
            # Run in background thread to avoid blocking admin UI
            threading.Thread(target=run_processing).start()

@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['document', 'chunk_index', 'page_number', 'created_at']
    list_filter = ['document', 'page_number']
    search_fields = ['chunk_text', 'document__title']
    
@admin.register(KnowledgeQuery)
class KnowledgeQueryAdmin(admin.ModelAdmin):
    list_display = ['user', 'query_text_preview', 'confidence_score', 'timestamp']
    list_filter = ['timestamp', 'confidence_score']
    search_fields = ['query_text', 'user__username']
    
    def query_text_preview(self, obj):
        return obj.query_text[:50] + '...' if len(obj.query_text) > 50 else obj.query_text
    query_text_preview.short_description = 'Query'
