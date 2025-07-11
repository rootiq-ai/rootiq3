from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # Database settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://alertuser:alertpass@localhost:5432/alertdb"
    )
    
    # ChromaDB settings
    CHROMADB_PATH: str = os.getenv("CHROMADB_PATH", "./chromadb_data")
    CHROMADB_COLLECTION: str = os.getenv("CHROMADB_COLLECTION", "alert_knowledge")
    
    # Ollama settings
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    
    # Embedding model
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", 
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # RCA settings
    MAX_CONTEXT_LENGTH: int = int(os.getenv("MAX_CONTEXT_LENGTH", "4000"))
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    TOP_K_SIMILAR: int = int(os.getenv("TOP_K_SIMILAR", "5"))
    
    # Alert grouping settings
    GROUPING_TIME_WINDOW: int = int(os.getenv("GROUPING_TIME_WINDOW", "300"))  # seconds
    
    class Config:
        env_file = ".env"


settings = Settings()
