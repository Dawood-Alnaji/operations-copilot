from rest_framework import serializers
from knowledge_base.models import Document, DocumentChunk, KnowledgeQuery


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for Document model"""
    
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    processing_status_display = serializers.CharField(source='get_processing_status_display', read_only=True)
    
    class Meta:
        model = Document
        fields = [
            'id', 'title', 'file', 'uploaded_by', 'uploaded_by_name',
            'upload_timestamp', 'file_hash', 'processing_status',
            'processing_status_display', 'metadata'
        ]
        read_only_fields = ['id', 'uploaded_by', 'upload_timestamp', 'file_hash', 'processing_status']


class DocumentUploadSerializer(serializers.Serializer):
    """Serializer for document upload requests"""
    
    file = serializers.FileField()
    title = serializers.CharField(max_length=255)
    metadata = serializers.JSONField(required=False)


class KnowledgeQueryRequestSerializer(serializers.Serializer):
    """Serializer for knowledge query requests"""
    
    query = serializers.CharField()
    top_k = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)


class SourceSerializer(serializers.Serializer):
    """Serializer for source citations"""
    
    document = serializers.CharField()
    page = serializers.IntegerField()
    document_id = serializers.IntegerField()


class KnowledgeQueryResponseSerializer(serializers.Serializer):
    """Serializer for knowledge query responses"""
    
    answer = serializers.CharField()
    sources = SourceSerializer(many=True)
    confidence = serializers.FloatField()


class KnowledgeQueryHistorySerializer(serializers.ModelSerializer):
    """Serializer for query history"""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    sources_count = serializers.SerializerMethodField()
    
    class Meta:
        model = KnowledgeQuery
        fields = [
            'id', 'user', 'user_name', 'query_text', 'llm_response',
            'confidence_score', 'timestamp', 'feedback_rating',
            'response_time_ms', 'sources_count'
        ]
        read_only_fields = ['id', 'user', 'timestamp']
    
    def get_sources_count(self, obj):
        return obj.retrieved_chunks.count()
