import os
import re
import logging
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

KNOWLEDGE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "knowledge.md"))
CHROMA_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "chroma_db"))

COLLECTION_NAME = "rrl_knowledge"
EMBEDDING_MODEL_NAME = "Qwen/Qwen3-Embedding-0.6B"

# We initialize these lazily to avoid heavy loading if not needed immediately
_chroma_client = None
_collection = None
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        # Use trust_remote_code=True in case Qwen model requires it
        _embedder = SentenceTransformer(EMBEDDING_MODEL_NAME, trust_remote_code=True)
    return _embedder

def get_chroma_collection():
    global _chroma_client, _collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        
        # Check if collection exists
        existing_collections = [c.name for c in _chroma_client.list_collections()]
        
        if COLLECTION_NAME in existing_collections:
            _collection = _chroma_client.get_collection(name=COLLECTION_NAME)
            logger.info("ChromaDB collection loaded successfully.")
        else:
            logger.info("ChromaDB collection not found. Initializing and ingesting RRL...")
            _collection = _chroma_client.create_collection(name=COLLECTION_NAME)
            _ingest_knowledge_base()
            
    return _collection

def _ingest_knowledge_base():
    """Parses knowledge.md by headers and ingests it into ChromaDB."""
    if not os.path.exists(KNOWLEDGE_PATH):
        logger.error(f"Knowledge base file not found at {KNOWLEDGE_PATH}")
        return

    with open(KNOWLEDGE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by markdown headers
    # We look for lines starting with # or ## and split there
    sections = re.split(r'(?m)^(#+ .*)$', content)
    
    chunks = []
    metadatas = []
    ids = []
    
    current_heading = "General"
    
    # sections will be: ['', '# Heading', 'content...', '## Subheading', 'more content...']
    # If content doesn't start with a heading, the first element is preamble.
    if sections[0].strip():
        chunks.append(sections[0].strip())
        metadatas.append({"section": current_heading, "source": "knowledge.md"})
        ids.append(f"chunk_0")
        
    chunk_idx = 1
    for i in range(1, len(sections), 2):
        if i + 1 < len(sections):
            heading = sections[i].strip()
            text = sections[i+1].strip()
            
            if text:
                chunks.append(text)
                # Remove the '#' from heading for clean metadata
                clean_heading = heading.lstrip('#').strip()
                metadatas.append({"section": clean_heading, "source": "knowledge.md"})
                ids.append(f"chunk_{chunk_idx}")
                chunk_idx += 1

    if not chunks:
        logger.warning("No chunks parsed from knowledge base.")
        return

    # Embed chunks
    embedder = get_embedder()
    embeddings = embedder.encode(chunks).tolist()
    
    _collection.add(
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )
    logger.info(f"Successfully ingested {len(chunks)} chunks into ChromaDB.")

def retrieve_rrl_context(query: str, top_k: int = 2) -> str:
    """Retrieves top-k relevant chunks from the RRL."""
    collection = get_chroma_collection()
    embedder = get_embedder()
    
    query_embedding = embedder.encode([query]).tolist()
    
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k
    )
    
    retrieved_docs = results['documents'][0]
    retrieved_metadatas = results['metadatas'][0]
    
    if not retrieved_docs:
        return ""
        
    logger.info(f"RAG Retrieval executed for query: '{query}'. Retrieved {len(retrieved_docs)} chunks.")
    
    context_str = "### Published Research Evidence (RRL)\n"
    for doc, meta in zip(retrieved_docs, retrieved_metadatas):
        section = meta.get('section', 'Unknown Section')
        source = meta.get('source', 'knowledge.md')
        context_str += f"**Source:** {source} | **Section:** {section}\n"
        context_str += f"{doc}\n\n"
        
    return context_str
