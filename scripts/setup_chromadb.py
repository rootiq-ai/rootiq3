#!/usr/bin/env python3
"""
ChromaDB setup script for Alert Monitoring MVP
Initializes vector database for RAG functionality
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.append(str(Path(__file__).parent.parent))

try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
except ImportError as e:
    print(f"❌ Error importing required packages: {e}")
    print("Please install required packages: pip install chromadb sentence-transformers")
    sys.exit(1)

# Import app modules
try:
    from backend.app.config.settings import settings
except ImportError as e:
    print(f"Error importing app settings: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)


def setup_chromadb():
    """Setup ChromaDB client and collection"""
    
    print("Setting up ChromaDB...")
    
    try:
        # Create ChromaDB data directory
        chromadb_path = Path(settings.CHROMADB_PATH)
        chromadb_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 ChromaDB directory: {chromadb_path.absolute()}")
        
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(
            path=str(chromadb_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        print("✅ ChromaDB client initialized")
        
        # List existing collections
        existing_collections = client.list_collections()
        print(f"📋 Existing collections: {[c.name for c in existing_collections]}")
        
        # Create or get the alert knowledge collection
        collection_name = settings.CHROMADB_COLLECTION
        
        try:
            # Try to get existing collection
            collection = client.get_collection(name=collection_name)
            print(f"✅ Found existing collection: {collection_name}")
            
            # Get collection stats
            count = collection.count()
            print(f"📊 Documents in collection: {count}")
            
        except Exception:
            # Create new collection
            collection = client.create_collection(
                name=collection_name,
                metadata={"description": "Alert knowledge base for RCA generation"}
            )
            print(f"✅ Created new collection: {collection_name}")
        
        return client, collection
        
    except Exception as e:
        print(f"❌ Error setting up ChromaDB: {e}")
        sys.exit(1)


def test_embedding_model():
    """Test the sentence transformer model"""
    
    print(f"Testing embedding model: {settings.EMBEDDING_MODEL}")
    
    try:
        # Load the model
        model = SentenceTransformer(settings.EMBEDDING_MODEL)
        print(f"✅ Embedding model loaded successfully")
        
        # Test encoding
        test_text = "Test alert: High CPU usage on web-server-01"
        embedding = model.encode(test_text)
        
        print(f"📊 Embedding dimension: {len(embedding)}")
        print(f"📊 Sample embedding values: {embedding[:5]}")
        
        return model
        
    except Exception as e:
        print(f"❌ Error with embedding model: {e}")
        print("This might take a few minutes on first run to download the model...")
        sys.exit(1)


def add_sample_documents(collection, model):
    """Add sample documents to test the setup"""
    
    print("Would you like to add sample documents for testing? (y/N): ", end="")
    choice = input().lower()
    
    if choice in ['y', 'yes']:
        print("Adding sample documents...")
        
        sample_docs = [
            {
                "text": "Alert: HighCPUUsage | Host: web-server-01 | Service: nginx | Severity: high | Message: CPU usage above 90% for 5 minutes",
                "metadata": {
                    "alert_id": "sample_001",
                    "host_name": "web-server-01",
                    "service_name": "nginx",
                    "severity": "high",
                    "type": "alert"
                }
            },
            {
                "text": "Alert: MemoryLeak | Host: web-server-01 | Service: java | Severity: critical | Message: Memory usage continuously increasing",
                "metadata": {
                    "alert_id": "sample_002",
                    "host_name": "web-server-01",
                    "service_name": "java",
                    "severity": "critical",
                    "type": "alert"
                }
            },
            {
                "text": "Alert Group: web-server-01 - postgresql | Host: web-server-01 | Service: postgresql | Alert Count: 3 | Severity Summary: {\"high\": 2, \"medium\": 1}",
                "metadata": {
                    "group_id": "sample_group_001",
                    "host_name": "web-server-01",
                    "service_name": "postgresql",
                    "alert_count": 3,
                    "type": "group"
                }
            },
            {
                "text": "Alert: DiskSpaceLow | Host: db-server-01 | Service: postgresql | Severity: medium | Message: Disk usage above 85%",
                "metadata": {
                    "alert_id": "sample_003",
                    "host_name": "db-server-01",
                    "service_name": "postgresql",
                    "severity": "medium",
                    "type": "alert"
                }
            },
            {
                "text": "Alert: NetworkTimeout | Host: api-gateway-01 | Service: nginx | Severity: high | Message: Upstream timeout errors increasing",
                "metadata": {
                    "alert_id": "sample_004",
                    "host_name": "api-gateway-01",
                    "service_name": "nginx",
                    "severity": "high",
                    "type": "alert"
                }
            }
        ]
        
        try:
            # Generate embeddings for all documents
            documents = [doc["text"] for doc in sample_docs]
            embeddings = model.encode(documents).tolist()
            metadatas = [doc["metadata"] for doc in sample_docs]
            ids = [f"sample_{i+1}" for i in range(len(sample_docs))]
            
            # Add to collection
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            
            print(f"✅ Added {len(sample_docs)} sample documents")
            
            # Test search
            test_search(collection, model)
            
        except Exception as e:
            print(f"⚠️ Warning: Could not add sample documents: {e}")


def test_search(collection, model):
    """Test similarity search functionality"""
    
    print("Testing similarity search...")
    
    try:
        # Test query
        query = "high cpu usage web server"
        query_embedding = model.encode(query).tolist()
        
        # Search
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=3,
            include=["documents", "metadatas", "distances"]
        )
        
        print(f"🔍 Search query: '{query}'")
        print(f"📊 Results found: {len(results['documents'][0])}")
        
        for i, doc in enumerate(results['documents'][0]):
            metadata = results['metadatas'][0][i]
            distance = results['distances'][0][i]
            similarity = 1 - distance
            
            print(f"\nResult {i+1} (Similarity: {similarity:.3f}):")
            print(f"  Document: {doc[:100]}...")
            print(f"  Type: {metadata.get('type', 'N/A')}")
            print(f"  Host: {metadata.get('host_name', 'N/A')}")
            print(f"  Service: {metadata.get('service_name', 'N/A')}")
        
        print("✅ Similarity search test successful")
        
    except Exception as e:
        print(f"⚠️ Warning: Search test failed: {e}")


def check_ollama_connection():
    """Check if Ollama is available"""
    
    print("Checking Ollama connection...")
    
    try:
        import ollama
        
        # Try to connect to Ollama
        client = ollama.Client(host=settings.OLLAMA_HOST)
        
        # List available models
        models = client.list()
        model_names = [model['name'] for model in models['models']]
        
        print(f"✅ Ollama connection successful")
        print(f"📋 Available models: {model_names}")
        
        if settings.OLLAMA_MODEL in model_names:
            print(f"✅ Target model '{settings.OLLAMA_MODEL}' is available")
        else:
            print(f"⚠️ Warning: Target model '{settings.OLLAMA_MODEL}' not found")
            print(f"   Run: ollama pull {settings.OLLAMA_MODEL}")
        
    except ImportError:
        print("⚠️ Warning: Ollama package not installed")
        print("   Install with: pip install ollama")
    except Exception as e:
        print(f"⚠️ Warning: Could not connect to Ollama: {e}")
        print(f"   Make sure Ollama is running on {settings.OLLAMA_HOST}")
        print("   Install Ollama: curl -fsSL https://ollama.ai/install.sh | sh")


def cleanup_collection(client, collection_name):
    """Cleanup/reset collection if needed"""
    
    print(f"Would you like to reset the collection '{collection_name}'? (y/N): ", end="")
    choice = input().lower()
    
    if choice in ['y', 'yes']:
        try:
            # Delete existing collection
            client.delete_collection(name=collection_name)
            print(f"🗑️ Deleted existing collection: {collection_name}")
            
            # Create new collection
            collection = client.create_collection(
                name=collection_name,
                metadata={"description": "Alert knowledge base for RCA generation"}
            )
            print(f"✅ Created fresh collection: {collection_name}")
            
            return collection
            
        except Exception as e:
            print(f"⚠️ Warning: Could not reset collection: {e}")
            return None
    
    return None


def main():
    """Main setup function"""
    
    print("🚀 Alert Monitoring MVP - ChromaDB Setup")
    print("=" * 50)
    
    # Check environment
    print(f"📋 ChromaDB Path: {settings.CHROMADB_PATH}")
    print(f"📋 Collection Name: {settings.CHROMADB_COLLECTION}")
    print(f"📋 Embedding Model: {settings.EMBEDDING_MODEL}")
    print(f"📋 Ollama Host: {settings.OLLAMA_HOST}")
    print(f"📋 Ollama Model: {settings.OLLAMA_MODEL}")
    print()
    
    # Setup steps
    try:
        # Setup ChromaDB
        client, collection = setup_chromadb()
        print()
        
        # Test embedding model
        model = test_embedding_model()
        print()
        
        # Check for collection reset
        reset_collection = cleanup_collection(client, settings.CHROMADB_COLLECTION)
        if reset_collection:
            collection = reset_collection
        print()
        
        # Add sample documents
        add_sample_documents(collection, model)
        print()
        
        # Check Ollama
        check_ollama_connection()
        print()
        
        print("🎉 ChromaDB setup completed successfully!")
        print()
        print("Configuration Summary:")
        print(f"• ChromaDB Path: {Path(settings.CHROMADB_PATH).absolute()}")
        print(f"• Collection: {settings.CHROMADB_COLLECTION}")
        print(f"• Documents: {collection.count()}")
        print(f"• Embedding Model: {settings.EMBEDDING_MODEL}")
        print()
        print("Next steps:")
        print("1. Make sure Ollama is running: ollama serve")
        print(f"2. Pull the model: ollama pull {settings.OLLAMA_MODEL}")
        print("3. Start the backend: cd backend && python -m app.main")
        print("4. Start the frontend: cd frontend && streamlit run streamlit_app.py")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
