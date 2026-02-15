from django.urls import path
from knowledge_base.views import (
    DocumentUploadView, DocumentListView, DocumentDeleteView,
    KnowledgeQueryView, KnowledgeQueryHistoryView
)

app_name = 'knowledge_base'

urlpatterns = [
    # Document Management
    path('documents/upload/', DocumentUploadView.as_view(), name='document-upload'),
    path('documents/', DocumentListView.as_view(), name='document-list'),
    path('documents/<int:document_id>/', DocumentDeleteView.as_view(), name='document-delete'),
    
    # Knowledge Query
    path('query/', KnowledgeQueryView.as_view(), name='knowledge-query'),
    path('history/', KnowledgeQueryHistoryView.as_view(), name='query-history'),
]
