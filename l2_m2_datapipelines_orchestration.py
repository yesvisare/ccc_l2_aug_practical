"""
Module 5.2: Data Pipelines & Orchestration
Implementation of Apache Airflow orchestration for automated RAG data refresh pipelines.

This module provides functions for:
- Detecting changed documents using checksums
- Processing documents in batches with parallel support
- Embedding document chunks
- Upserting to Pinecone vector database
- Handling document deletions

Based on TVH Framework v2.0: Includes explicit failure handling and cost awareness.
"""
import os
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_file_checksum(file_path: str) -> str:
    """
    Calculate SHA256 checksum for a file.

    Args:
        file_path: Path to the file

    Returns:
        Hex digest of the file's SHA256 hash

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise IOError(f"Cannot read file: {file_path}")


def detect_changed_documents(
    documents_path: str,
    checksums_file: str,
    file_extensions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Scan document directory and identify files that changed since last run.

    This is the core change detection function that enables incremental indexing.
    It compares current file checksums against stored checksums from the previous run.

    Args:
        documents_path: Path to directory containing documents
        checksums_file: Path to JSON file storing checksums
        file_extensions: List of file extensions to process (default: pdf, docx, txt)

    Returns:
        Dictionary with:
            - changed_files: List of file paths that were added or modified
            - deleted_files: List of file paths that were removed
            - current_checksums: Dict mapping file paths to checksums

    Example:
        >>> result = detect_changed_documents('/data/docs', '/data/checksums.json')
        >>> print(f"Changed: {len(result['changed_files'])}")
        Changed: 12
    """
    if file_extensions is None:
        file_extensions = ['.pdf', '.docx', '.txt', '.md']

    # Load previous checksums
    try:
        with open(checksums_file, 'r') as f:
            previous_checksums = json.load(f)
        logger.info(f"Loaded {len(previous_checksums)} previous checksums")
    except FileNotFoundError:
        previous_checksums = {}
        logger.info("No previous checksums found, treating all files as new")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid checksums file: {e}")
        previous_checksums = {}

    changed_files = []
    current_checksums = {}

    # Scan directory
    if not os.path.exists(documents_path):
        logger.error(f"Documents path does not exist: {documents_path}")
        raise FileNotFoundError(f"Documents path not found: {documents_path}")

    logger.info(f"Scanning directory: {documents_path}")
    file_count = 0

    for root, _, files in os.walk(documents_path):
        for filename in files:
            if not any(filename.endswith(ext) for ext in file_extensions):
                continue

            file_path = os.path.join(root, filename)
            file_count += 1

            try:
                # Calculate current checksum
                file_hash = calculate_file_checksum(file_path)
                current_checksums[file_path] = file_hash

                # Check if changed
                if file_path not in previous_checksums:
                    changed_files.append(file_path)
                    logger.info(f"NEW: {file_path}")
                elif previous_checksums[file_path] != file_hash:
                    changed_files.append(file_path)
                    logger.info(f"MODIFIED: {file_path}")

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                continue

    # Check for deletions
    deleted_files = list(set(previous_checksums.keys()) - set(current_checksums.keys()))
    for deleted_path in deleted_files:
        logger.info(f"DELETED: {deleted_path}")

    logger.info(f"Scanned {file_count} files: {len(changed_files)} changed, {len(deleted_files)} deleted")

    # Save current checksums for next run
    try:
        os.makedirs(os.path.dirname(checksums_file), exist_ok=True)
        with open(checksums_file, 'w') as f:
            json.dump(current_checksums, f, indent=2)
        logger.info(f"Saved checksums to {checksums_file}")
    except Exception as e:
        logger.error(f"Failed to save checksums: {e}")

    return {
        'changed_files': changed_files,
        'deleted_files': deleted_files,
        'current_checksums': current_checksums
    }


def chunk_document(
    file_path: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50
) -> List[Dict[str, Any]]:
    """
    Split document into overlapping chunks for embedding.

    Args:
        file_path: Path to document file
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Number of overlapping characters between chunks

    Returns:
        List of chunk dictionaries with 'text', 'index', and 'metadata'

    Example:
        >>> chunks = chunk_document('doc.txt', chunk_size=512)
        >>> print(f"Created {len(chunks)} chunks")
        Created 24 chunks
    """
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        if not content.strip():
            logger.warning(f"Empty file: {file_path}")
            return []

        chunks = []
        start = 0

        while start < len(content):
            end = start + chunk_size
            chunk_text = content[start:end]

            # Don't create tiny final chunks
            if len(chunk_text.strip()) < 50 and len(chunks) > 0:
                break

            chunks.append({
                'text': chunk_text,
                'index': len(chunks),
                'metadata': {
                    'file_path': file_path,
                    'chunk_index': len(chunks),
                    'start_char': start,
                    'end_char': end
                }
            })

            start = end - chunk_overlap

        logger.info(f"Created {len(chunks)} chunks from {file_path}")
        return chunks

    except Exception as e:
        logger.error(f"Error chunking document {file_path}: {e}")
        raise


def embed_chunks(
    chunks: List[Dict[str, Any]],
    openai_client=None,
    model: str = "text-embedding-3-small"
) -> List[List[float]]:
    """
    Generate embeddings for document chunks using OpenAI.

    Args:
        chunks: List of chunk dictionaries from chunk_document()
        openai_client: OpenAI client instance (optional, will skip if None)
        model: OpenAI embedding model to use

    Returns:
        List of embedding vectors (each is a list of floats)

    Note:
        If openai_client is None, returns empty list (graceful degradation)
    """
    if openai_client is None:
        logger.warning("⚠️ OpenAI client not provided, skipping embeddings")
        return []

    if not chunks:
        return []

    try:
        texts = [chunk['text'] for chunk in chunks]

        # Batch embed for efficiency (OpenAI supports up to 2048 inputs)
        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]

            response = openai_client.embeddings.create(
                model=model,
                input=batch_texts
            )

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            logger.info(f"Embedded batch {i//batch_size + 1} ({len(batch_texts)} chunks)")

        logger.info(f"Generated {len(all_embeddings)} embeddings")
        return all_embeddings

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise


def process_document_batch(
    file_paths: List[str],
    openai_client=None,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    embedding_model: str = "text-embedding-3-small"
) -> List[Dict[str, Any]]:
    """
    Process a batch of documents: chunk and embed.

    This function is designed to be called by parallel workers.

    Args:
        file_paths: List of document file paths to process
        openai_client: OpenAI client for embeddings
        chunk_size: Size of document chunks
        chunk_overlap: Overlap between chunks
        embedding_model: OpenAI model for embeddings

    Returns:
        List of processed batch dictionaries with file_path, chunks, and embeddings
    """
    processed_batches = []

    for file_path in file_paths:
        try:
            logger.info(f"Processing: {file_path}")

            # Chunk the document
            chunks = chunk_document(file_path, chunk_size, chunk_overlap)

            if not chunks:
                logger.warning(f"No chunks created for {file_path}")
                continue

            # Embed chunks
            embeddings = embed_chunks(chunks, openai_client, embedding_model)

            # Prepare batch
            batch = {
                'file_path': file_path,
                'chunks': chunks,
                'embeddings': embeddings,
                'processed_at': datetime.now().isoformat()
            }
            processed_batches.append(batch)

        except Exception as e:
            logger.error(f"ERROR processing {file_path}: {e}")
            # Don't fail entire batch for one document
            continue

    logger.info(f"Successfully processed {len(processed_batches)}/{len(file_paths)} documents")
    return processed_batches


def upsert_to_pinecone(
    processed_batches: List[Dict[str, Any]],
    pinecone_index=None,
    batch_size: int = 100
) -> int:
    """
    Upsert processed documents to Pinecone vector database.

    Args:
        processed_batches: List of processed document batches
        pinecone_index: Pinecone index instance (optional, will skip if None)
        batch_size: Number of vectors to upsert per API call

    Returns:
        Total number of vectors upserted

    Note:
        If pinecone_index is None, logs warning and returns 0 (graceful degradation)
    """
    if pinecone_index is None:
        logger.warning("⚠️ Pinecone index not provided, skipping upsert")
        return 0

    if not processed_batches:
        logger.info("No batches to upsert")
        return 0

    total_vectors = 0

    for batch in processed_batches:
        file_path = batch['file_path']
        chunks = batch['chunks']
        embeddings = batch.get('embeddings', [])

        if not embeddings:
            logger.warning(f"No embeddings for {file_path}, skipping upsert")
            continue

        try:
            # Prepare vectors for upsert
            vectors_to_upsert = []

            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                vector_id = f"{hashlib.sha256(file_path.encode()).hexdigest()}_{i}"

                metadata = {
                    'text': chunk['text'][:1000],  # Limit metadata size
                    'file_path': file_path,
                    'chunk_index': i,
                    'updated_at': datetime.now().isoformat(),
                }

                vectors_to_upsert.append({
                    'id': vector_id,
                    'values': embedding,
                    'metadata': metadata
                })

            # Upsert in batches
            for i in range(0, len(vectors_to_upsert), batch_size):
                batch_slice = vectors_to_upsert[i:i + batch_size]
                pinecone_index.upsert(vectors=batch_slice)
                total_vectors += len(batch_slice)

            logger.info(f"Upserted {len(vectors_to_upsert)} vectors for {file_path}")

        except Exception as e:
            logger.error(f"Error upserting {file_path}: {e}")
            continue

    logger.info(f"Successfully upserted {total_vectors} total vectors")
    return total_vectors


def handle_deletions(
    deleted_files: List[str],
    pinecone_index=None
) -> int:
    """
    Remove vectors for deleted documents from Pinecone.

    Args:
        deleted_files: List of file paths that were deleted
        pinecone_index: Pinecone index instance (optional, will skip if None)

    Returns:
        Number of file deletions processed

    Note:
        If pinecone_index is None, logs warning and returns 0 (graceful degradation)
    """
    if pinecone_index is None:
        logger.warning("⚠️ Pinecone index not provided, skipping deletions")
        return 0

    if not deleted_files:
        logger.info("No deletions to handle")
        return 0

    deletions_processed = 0

    for file_path in deleted_files:
        try:
            # Delete all vectors with this file_path in metadata
            pinecone_index.delete(
                filter={'file_path': {'$eq': file_path}}
            )
            logger.info(f"Deleted vectors for: {file_path}")
            deletions_processed += 1

        except Exception as e:
            logger.error(f"Error deleting vectors for {file_path}: {e}")
            continue

    logger.info(f"Handled {deletions_processed} deletions")
    return deletions_processed


def run_incremental_refresh_pipeline(
    documents_path: str,
    checksums_file: str,
    openai_client=None,
    pinecone_index=None,
    max_workers: int = 1
) -> Dict[str, Any]:
    """
    Run the full incremental refresh pipeline.

    This is the main orchestration function that:
    1. Detects changed documents
    2. Processes them (chunks and embeds)
    3. Upserts to Pinecone
    4. Handles deletions

    Args:
        documents_path: Path to documents directory
        checksums_file: Path to checksums storage
        openai_client: OpenAI client instance
        pinecone_index: Pinecone index instance
        max_workers: Number of parallel workers (1 = sequential)

    Returns:
        Dictionary with pipeline execution summary
    """
    start_time = time.time()
    logger.info("=== Starting Incremental Refresh Pipeline ===")

    # Step 1: Detect changes
    logger.info("Step 1: Detecting changed documents...")
    changes = detect_changed_documents(documents_path, checksums_file)

    changed_files = changes['changed_files']
    deleted_files = changes['deleted_files']

    if not changed_files and not deleted_files:
        logger.info("No changes detected. Pipeline complete.")
        return {
            'status': 'success',
            'changes_detected': False,
            'duration_seconds': time.time() - start_time
        }

    # Step 2: Process documents
    logger.info(f"Step 2: Processing {len(changed_files)} changed documents...")
    if max_workers > 1:
        logger.info(f"Using {max_workers} parallel workers")
        # Note: Actual parallel execution would use multiprocessing or Celery
        # For this implementation, we process sequentially
        logger.warning("Parallel processing requires Celery/Airflow setup")

    processed_batches = process_document_batch(
        changed_files,
        openai_client=openai_client
    )

    # Step 3: Upsert to Pinecone
    logger.info("Step 3: Upserting to Pinecone...")
    vectors_upserted = upsert_to_pinecone(processed_batches, pinecone_index)

    # Step 4: Handle deletions
    logger.info("Step 4: Handling deletions...")
    deletions_handled = handle_deletions(deleted_files, pinecone_index)

    duration = time.time() - start_time

    summary = {
        'status': 'success',
        'changes_detected': True,
        'files_changed': len(changed_files),
        'files_deleted': len(deleted_files),
        'files_processed': len(processed_batches),
        'vectors_upserted': vectors_upserted,
        'deletions_handled': deletions_handled,
        'duration_seconds': round(duration, 2)
    }

    logger.info("=== Pipeline Complete ===")
    logger.info(f"Summary: {summary}")

    return summary


if __name__ == "__main__":
    """
    CLI usage example with graceful degradation when services are unavailable.
    """
    print("=== M5.2: Data Pipelines & Orchestration ===\n")

    # Load configuration
    from config import (
        DATA_DIR, CHECKSUM_FILE, get_clients, validate_config
    )

    # Validate configuration
    config_valid = validate_config()

    if not config_valid:
        print("⚠️ Configuration incomplete. Running in demo mode (no API calls).\n")

    # Get clients (may be None if keys missing)
    clients = get_clients()

    # Example 1: Detect changes only
    print("Example 1: Detecting changed documents...")
    try:
        # Create example directory if it doesn't exist
        os.makedirs(DATA_DIR, exist_ok=True)

        changes = detect_changed_documents(DATA_DIR, CHECKSUM_FILE)
        print(f"  Changed files: {len(changes['changed_files'])}")
        print(f"  Deleted files: {len(changes['deleted_files'])}\n")
    except Exception as e:
        print(f"  Error: {e}\n")

    # Example 2: Full pipeline (will skip API calls if clients are None)
    print("Example 2: Running full incremental refresh pipeline...")
    try:
        result = run_incremental_refresh_pipeline(
            documents_path=DATA_DIR,
            checksums_file=CHECKSUM_FILE,
            openai_client=clients['openai'],
            pinecone_index=clients['pinecone'],
            max_workers=1
        )
        print(f"  Status: {result['status']}")
        print(f"  Duration: {result['duration_seconds']}s")
        print(f"  Files processed: {result.get('files_processed', 0)}")
        print(f"  Vectors upserted: {result.get('vectors_upserted', 0)}\n")
    except Exception as e:
        print(f"  Error: {e}\n")

    print("Note: This is a simplified example. For production, use Airflow DAGs.")
    print("See L2_M2_DataPipelines_Orchestration.ipynb for full implementation.")
