#!/usr/bin/env python3
"""
Usage:
    python test_rag.py                    # Interactive mode
    python test_rag.py --query "..."      # Single query mode
    python test_rag.py --rebuild          # Force rebuild index
    python test_rag.py --stats            # Show statistics only
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to import vector_store
sys.path.insert(0, str(Path(__file__).parent))
from vector_store import VectorStore


def load_config():
    """Load configuration from RAG.env file in llm-verif root."""
    config_file = Path('llm-verif/llm/RAG.env')

    if not config_file.exists():
        print(f"Warning: Config file not found at {config_file}")
        print("Using default configuration...")
        return {
            'corpus_dir': 'llm-verif/rag_corpus',
            'index_path': 'llm-verif/.ragindex',
            'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2',
            'chunk_size': 256,
            'chunk_overlap': 32,
            'top_k': 5,
            'index_name': 'default'
        }

    # Load .env file
    load_dotenv(config_file)

    return {
        'corpus_dir': os.getenv('RAG_CORPUS_DIR', 'llm-verif/rag_corpus'),
        'index_path': os.getenv('RAG_INDEX_PATH', 'llm-verif/.ragindex'),
        'embedding_model': os.getenv('RAG_EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2'),
        'chunk_size': int(os.getenv('RAG_CHUNK_SIZE', '256')),
        'chunk_overlap': int(os.getenv('RAG_CHUNK_OVERLAP', '32')),
        'top_k': int(os.getenv('RAG_TOP_K', '5')),
        'index_name': os.getenv('RAG_INDEX_NAME', 'default')
    }


def print_separator(char='=', length=80):
    """Print a separator line."""
    print(char * length)


def display_results(results, query):
    """Display retrieval results in a formatted way."""
    print_separator()
    print(f"QUERY: {query}")
    print_separator()

    if not results:
        print("No results found.")
        return

    for i, (chunk, file_path, distance) in enumerate(results, 1):
        filename = os.path.basename(file_path)
        similarity_score = 1 / (1 + distance)  # Convert distance to similarity (0-1 range)

        print(f"\n[Result {i}]")
        print(f"File: {filename}")
        print(f"Path: {file_path}")
        print(f"Distance: {distance:.4f} | Similarity: {similarity_score:.4f}")
        print(f"\nContent Preview:")
        print("-" * 80)

        # Show first 300 characters of chunk
        preview = chunk[:300] + "..." if len(chunk) > 300 else chunk
        print(preview)
        print("-" * 80)


def run_predefined_tests(vector_store, top_k):
    """Run a set of predefined test queries."""
    print("\n" + "=" * 80)
    print("RUNNING PREDEFINED TEST QUERIES")
    print("=" * 80)

    test_queries = [
        "How do I write a SystemVerilog testbench?",
        "What is the basic structure of a testbench?",
        "How to generate a clock signal in Verilog?",
        "How do I check outputs in a testbench?",
        "What are common testbench mistakes to avoid?",
        "How to use assertions in SystemVerilog?",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}\nTest Query {i}/{len(test_queries)}\n{'='*80}")
        results = vector_store.retrieve_relevant_chunks(query, top_k=top_k)
        display_results(results, query)
        print()

    print_separator()
    print("All predefined tests completed!")


def interactive_mode(vector_store, top_k):
    """Run in interactive query mode."""
    print("\n" + "=" * 80)
    print("INTERACTIVE RAG TESTING MODE")
    print("=" * 80)
    print("\nEnter your queries below. Type 'quit', 'exit', or 'q' to stop.")
    print("Type 'stats' to show vector store statistics.")
    print("Type 'test' to run predefined test queries.")
    print_separator()

    while True:
        try:
            query = input("\nQuery: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("Exiting interactive mode. Goodbye!")
                break

            if query.lower() == 'stats':
                print("\n" + vector_store.get_stats())
                continue

            if query.lower() == 'test':
                run_predefined_tests(vector_store, top_k)
                continue

            if not query:
                print("Please enter a query.")
                continue

            results = vector_store.retrieve_relevant_chunks(query, top_k=top_k)
            display_results(results, query)

        except KeyboardInterrupt:
            print("\n\nInterrupted. Exiting...")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Test RAG system independently")
    parser.add_argument('--query', '-q', type=str, help='Single query to test')
    parser.add_argument('--rebuild', '-r', action='store_true', help='Force rebuild index')
    parser.add_argument('--stats', '-s', action='store_true', help='Show statistics only')
    parser.add_argument('--test', '-t', action='store_true', help='Run predefined test queries')
    parser.add_argument('--top-k', '-k', type=int, help='Number of results to retrieve')

    # Performance tuning arguments
    parser.add_argument('--device', type=str, choices=['cuda', 'cpu'], help='Device for embeddings (cuda/cpu)')
    parser.add_argument('--batch-size', type=int, help='Batch size for encoding (default: 32, try 64-128 for GPU)')
    parser.add_argument('--workers', type=int, help='Number of CPU workers for encoding')

    args = parser.parse_args()

    # Load configuration
    print("Loading configuration...")
    config = load_config()

    print(f"\nConfiguration:")
    print(f"  Corpus Directory: {config['corpus_dir']}")
    print(f"  Index Path: {config['index_path']}")
    print(f"  Embedding Model: {config['embedding_model']}")
    print(f"  Chunk Size: {config['chunk_size']}")
    print(f"  Chunk Overlap: {config['chunk_overlap']}")
    print(f"  Default Top-K: {config['top_k']}")

    # Override top_k if specified
    top_k = args.top_k if args.top_k else config['top_k']

    # Initialize VectorStore with performance tuning
    print("\nInitializing VectorStore...")
    try:
        # Prepare initialization parameters
        init_kwargs = {
            'directory': config['corpus_dir'],
            'chunk_size': config['chunk_size'],
            'chunk_overlap': config['chunk_overlap'],
            'index_path': config['index_path'],
            'model_name': config['embedding_model']
        }

        # Add performance tuning parameters if specified
        if args.device:
            init_kwargs['device'] = args.device
        if args.batch_size:
            init_kwargs['batch_size'] = args.batch_size
        if args.workers:
            init_kwargs['num_workers'] = args.workers

        vector_store = VectorStore(**init_kwargs)
    except Exception as e:
        print(f"Error initializing VectorStore: {e}")
        sys.exit(1)

    # Try to load existing index or build new one
    if args.rebuild:
        print("\nForce rebuilding index...")
        try:
            vector_store.create_index()
            vector_store.save_index(name=config['index_name'])
        except Exception as e:
            print(f"Error building index: {e}")
            sys.exit(1)
    else:
        print(f"\nAttempting to load existing index '{config['index_name']}'...")
        loaded = vector_store.load_index(name=config['index_name'])

        if not loaded:
            print("No existing index found. Building new index...")
            try:
                vector_store.create_index()
                vector_store.save_index(name=config['index_name'])
            except Exception as e:
                print(f"Error building index: {e}")
                sys.exit(1)

    # Show stats if requested
    if args.stats:
        print("\n" + vector_store.get_stats())
        return

    # Run predefined tests if requested
    if args.test:
        run_predefined_tests(vector_store, top_k)
        return

    # Single query mode
    if args.query:
        results = vector_store.retrieve_relevant_chunks(args.query, top_k=top_k)
        display_results(results, args.query)
        return

    # Interactive mode (default)
    interactive_mode(vector_store, top_k)


if __name__ == "__main__":
    main()
