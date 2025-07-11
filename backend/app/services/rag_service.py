from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import uuid
import json
from loguru import logger
import os

from app.config.settings import settings
from app.models.alert import Alert
from app.models.group import AlertGroup


class RAGService:
    def __init__(self):
        self.logger = logger
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None
        self._initialize_chromadb()
        self._initialize_embedding_model()
    
    def _initialize_chromadb(self):
        """Initialize ChromaDB client and collection"""
        try:
            # Create ChromaDB data directory if it doesn't exist
            os.makedirs(settings.CHROMADB_PATH, exist_ok=True)
            
            # Initialize ChromaDB client
            self.chroma_client = chromadb.PersistentClient(
                path=settings.CHROMADB_PATH,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            self.collection = self.chroma_client.get_or_create_collection(
                name=settings.CHROMADB_COLLECTION,
                metadata={"description": "Alert knowledge base for RCA generation"}
            )
            
            self.logger.info(f"ChromaDB initialized with collection: {settings.CHROMADB_COLLECTION}")
            
        except Exception as e:
            self.logger.error(f"Error initializing ChromaDB: {e}")
            raise
    
    def _initialize_embedding_model(self):
        """Initialize sentence transformer model for embeddings"""
        try:
            self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            self.logger.info(f"Embedding model loaded: {settings.EMBEDDING_MODEL}")
        except Exception as e:
            self.logger.error(f"Error loading embedding model: {e}")
            raise
    
    async def add_alert_to_knowledge_base(self, alert: Alert):
        """
        Add alert information to the knowledge base
        
        Args:
            alert: Alert object to add
        """
        try:
            # Create document text from alert
            doc_text = self._create_alert_document(alert)
            
            # Generate embedding
            embedding = self.embedding_model.encode(doc_text).tolist()
            
            # Prepare metadata
            metadata = {
                "alert_id": alert.id,
                "host_name": alert.host_name,
                "service_name": alert.service_name,
                "alert_name": alert.alert_name,
                "severity": alert.severity,
                "monitoring_system": alert.monitoring_system,
                "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
                "type": "alert"
            }
            
            # Add to collection
            self.collection.add(
                documents=[doc_text],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[f"alert_{alert.id}"]
            )
            
            self.logger.info(f"Added alert {alert.id} to knowledge base")
            
        except Exception as e:
            self.logger.error(f"Error adding alert to knowledge base: {e}")
            raise
    
    async def add_group_to_knowledge_base(self, group: AlertGroup, alerts: List[Alert]):
        """
        Add alert group information to the knowledge base
        
        Args:
            group: AlertGroup object
            alerts: List of alerts in the group
        """
        try:
            # Create document text from group and its alerts
            doc_text = self._create_group_document(group, alerts)
            
            # Generate embedding
            embedding = self.embedding_model.encode(doc_text).tolist()
            
            # Prepare metadata
            metadata = {
                "group_id": group.id,
                "host_name": group.host_name,
                "service_name": group.service_name,
                "alert_count": group.alert_count,
                "severity_summary": json.dumps(group.severity_summary),
                "timestamp": group.created_at.isoformat() if group.created_at else None,
                "type": "group"
            }
            
            # Add to collection
            self.collection.add(
                documents=[doc_text],
                embeddings=[embedding],
                metadatas=[metadata],
                ids=[f"group_{group.id}"]
            )
            
            self.logger.info(f"Added group {group.id} to knowledge base")
            
        except Exception as e:
            self.logger.error(f"Error adding group to knowledge base: {e}")
            raise
    
    async def search_similar_incidents(self, query: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Search for similar incidents in the knowledge base
        
        Args:
            query: Search query
            limit: Maximum number of results (uses TOP_K_SIMILAR if None)
            
        Returns:
            List of similar incidents with metadata
        """
        try:
            if limit is None:
                limit = settings.TOP_K_SIMILAR
            
            # Generate embedding for query
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Search in collection
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            similar_incidents = []
            if results['documents'][0]:  # Check if we have results
                for i, doc in enumerate(results['documents'][0]):
                    similar_incidents.append({
                        "document": doc,
                        "metadata": results['metadatas'][0][i],
                        "similarity_score": 1 - results['distances'][0][i]  # Convert distance to similarity
                    })
            
            # Filter by similarity threshold
            filtered_incidents = [
                incident for incident in similar_incidents
                if incident['similarity_score'] >= settings.SIMILARITY_THRESHOLD
            ]
            
            self.logger.info(f"Found {len(filtered_incidents)} similar incidents for query")
            return filtered_incidents
            
        except Exception as e:
            self.logger.error(f"Error searching similar incidents: {e}")
            raise
    
    def _create_alert_document(self, alert: Alert) -> str:
        """
        Create a document string from an alert for embedding
        
        Args:
            alert: Alert object
            
        Returns:
            Document string
        """
        doc_parts = [
            f"Alert: {alert.alert_name}",
            f"Host: {alert.host_name}",
            f"Service: {alert.service_name}",
            f"Severity: {alert.severity}",
            f"Message: {alert.message}",
            f"Monitoring System: {alert.monitoring_system}"
        ]
        
        if alert.details:
            doc_parts.append(f"Details: {json.dumps(alert.details)}")
        
        return " | ".join(doc_parts)
    
    def _create_group_document(self, group: AlertGroup, alerts: List[Alert]) -> str:
        """
        Create a document string from an alert group for embedding
        
        Args:
            group: AlertGroup object
            alerts: List of alerts in the group
            
        Returns:
            Document string
        """
        doc_parts = [
            f"Alert Group: {group.name}",
            f"Host: {group.host_name}",
            f"Service: {group.service_name}",
            f"Alert Count: {group.alert_count}",
            f"Severity Summary: {json.dumps(group.severity_summary)}"
        ]
        
        # Add sample alert messages
        if alerts:
            sample_messages = [alert.message for alert in alerts[:3]]  # First 3 alerts
            doc_parts.append(f"Sample Messages: {' | '.join(sample_messages)}")
        
        return " | ".join(doc_parts)
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge base collection
        
        Returns:
            Dictionary with collection statistics
        """
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "collection_name": settings.CHROMADB_COLLECTION
            }
        except Exception as e:
            self.logger.error(f"Error getting collection stats: {e}")
            return {"error": str(e)}


# Create service instance
rag_service = RAGService()
