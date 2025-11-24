import os
import pickle
from datetime import datetime
from pathlib import Path
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# Check for GPU/acceleration support
try:
    import torch
    TORCH_AVAILABLE = True
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    if DEVICE == "cuda":
        print(f"GPU detected: {torch.cuda.get_device_name(0)}")
        print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    else:
        print("No GPU detected. Using CPU for embeddings.")
except ImportError:
    TORCH_AVAILABLE = False
    DEVICE = "cpu"
    print("PyTorch not available. Using CPU for embeddings.")

# Optional PDF processing dependencies
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except Exception as e:
    print(f"Warning: PyMuPDF (fitz) not available - PDF processing will be disabled")
    print(f"  Error: {e}")
    FITZ_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except Exception as e:
    print(f"Warning: pdfplumber not available - PDF table extraction will be disabled")
    PDFPLUMBER_AVAILABLE = False

# Optional HJSON support
try:
    import hjson
    HJSON_AVAILABLE = True
except Exception as e:
    print(f"Warning: hjson not available - HJSON file processing will be disabled")
    HJSON_AVAILABLE = False

class VectorStore:
    def __init__(self, directory, chunk_size=256, chunk_overlap=32, index_path=None,
                 model_name='sentence-transformers/all-MiniLM-L6-v2',
                 device=None, batch_size=32, num_workers=None, corpus_paths=None, index_name=None):
        """
        Initialize VectorStore with configurable parameters.

        Args:
            directory: Path to corpus directory containing documents
            chunk_size: Number of tokens per chunk (default: 256)
            chunk_overlap: Number of overlapping tokens between chunks (default: 32)
            index_path: Path to save/load persisted index (default: None, creates in .ragindex/)
            model_name: Name of sentence-transformers model (default: all-MiniLM-L6-v2)
            device: Device for embeddings ('cuda', 'cpu', or None for auto-detect)
            batch_size: Batch size for encoding (default: 32, increase for GPU)
            num_workers: Number of CPU workers (default: auto-detect)
            corpus_paths: Optional list of additional files/directories to include in the corpus
            index_name: Optional default name used for saving/loading the index
        """
        print("Initializing VectorStore...")
        self.directory = Path(directory)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.index_name = index_name

        # Set up device
        if device is None:
            self.device = DEVICE
        else:
            self.device = device

        self.batch_size = batch_size

        # Auto-detect number of workers if not specified
        if num_workers is None:
            import multiprocessing
            self.num_workers = max(1, multiprocessing.cpu_count() - 1)
        else:
            self.num_workers = num_workers

        # Set up index persistence path
        if index_path is None:
            project_root = Path(__file__).parent.parent.parent
            self.index_path = project_root / '.ragindex'
        else:
            self.index_path = Path(index_path)

        self.index_path.mkdir(parents=True, exist_ok=True)

        # Initialize model
        try:
            print(f"Loading embedding model: {model_name}")
            print(f"Using device: {self.device}")
            print(f"Batch size: {self.batch_size}")
            print(f"Workers: {self.num_workers}")
            self.model = SentenceTransformer(model_name, device=self.device)
            print(f"Model loaded successfully. Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
        except Exception as e:
            raise RuntimeError(f"Failed to load embedding model '{model_name}': {e}")

        # Core data structures
        self.all_chunks = []
        self.file_paths = []
        self.index = None
        self.corpus_paths = self._normalize_corpus_paths(corpus_paths, directory)

    def _normalize_corpus_paths(self, corpus_paths, directory) -> list[Path]:
        """
        Normalize corpus inputs into a list of valid Paths.
        Includes the legacy `directory` argument by default.
        """
        collected = []
        inputs = corpus_paths if corpus_paths else [directory]
        for path in inputs:
            p = Path(path)
            if p.exists():
                collected.append(p)
            else:
                print(f"Warning: corpus path does not exist and will be skipped: {p}")

        if not collected:
            raise FileNotFoundError("No valid corpus paths provided for VectorStore.")

        return collected

    def _ingest_file(self, file_path: str | Path) -> int:
        """
        Process a single file and add its chunks to the store.

        Returns:
            int: 1 if the file was processed, 0 otherwise
        """
        file_path = str(file_path)
        filename = os.path.basename(file_path)

        try:
            if filename.lower().endswith('.pdf'):
                if not FITZ_AVAILABLE:
                    print(f"Skipping PDF: {filename} (PyMuPDF not available)")
                    return 0
                print(f"Processing PDF: {filename}")
                text = self.extract_text_from_pdf(file_path)
                if text.strip():  # Only process if text was extracted
                    for chunk in self.chunk_text(text):
                        if chunk.strip():  # Skip empty chunks
                            self.all_chunks.append(chunk)
                            self.file_paths.append(file_path)

                tables = self.extract_tables_from_pdf(file_path)
                for table in tables:
                    if table:  # Only process non-empty tables
                        table_str = "\n".join(["\t".join(map(str, row)) for row in table if row])
                        for chunk in self.chunk_text(f"Table:\n{table_str}"):
                            if chunk.strip():
                                self.all_chunks.append(chunk)
                                self.file_paths.append(file_path)

                captions = self.extract_graphics_captions(file_path)
                for caption in captions:
                    for chunk in self.chunk_text(caption):
                        if chunk.strip():
                            self.all_chunks.append(chunk)
                            self.file_paths.append(file_path)
                return 1

            elif filename.lower().endswith(('.md', '.txt', '.sv', '.svh', '.v', '.vh', '.hjson')):
                # Determine file type for better logging
                if filename.lower().endswith(('.sv', '.svh', '.v', '.vh')):
                    print(f"Processing Verilog/SystemVerilog file: {filename}")
                elif filename.lower().endswith('.hjson'):
                    print(f"Processing HJSON file: {filename}")
                else:
                    print(f"Processing text file: {filename}")

                # Read file based on type
                if filename.lower().endswith('.hjson'):
                    text = self.read_hjson_file(file_path)
                else:
                    text = self.read_text_file(file_path)

                if text.strip():
                    for chunk in self.chunk_text(text):
                        if chunk.strip():
                            self.all_chunks.append(chunk)
                            self.file_paths.append(file_path)
                    return 1

        except Exception as e:
            print(f"Error processing {filename}: {e}")

        return 0

    def extract_text_from_pdf(self, pdf_path):
        if not FITZ_AVAILABLE:
            print(f"Warning: Cannot process PDF {pdf_path} - PyMuPDF not available")
            return ""
        text = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
        return text

    def extract_tables_from_pdf(self, pdf_path):
        if not PDFPLUMBER_AVAILABLE:
            return []
        tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables += page.extract_tables()
        return tables

    def extract_graphics_captions(self, pdf_path):
        if not FITZ_AVAILABLE:
            return []
        captions = []
        with fitz.open(pdf_path) as doc:
            for page in doc:
                for img_index, img in enumerate(page.get_images(full=True)):
                    caption = f"Graphic {img_index + 1}: Image found on page {page.number + 1}"
                    captions.append(caption)
        return captions

    def read_text_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Failed to read {file_path}: {e}")
            return ""

    def read_hjson_file(self, file_path):
        if not HJSON_AVAILABLE:
            return ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = hjson.load(f)

            # Convert HJSON object to readable text
            text_parts = []
            self._extract_hjson_text(data, text_parts)
            return "\n".join(text_parts)
        except Exception as e:
            print(f"Warning: Failed to read HJSON {file_path}: {e}")
            return ""

    def _extract_hjson_text(self, obj, text_parts, depth=0):
        indent = "  " * depth

        if isinstance(obj, dict):
            for key, value in obj.items():
                # Add key as header
                text_parts.append(f"{indent}{key}:")
                if isinstance(value, (dict, list)):
                    self._extract_hjson_text(value, text_parts, depth + 1)
                else:
                    text_parts.append(f"{indent}  {str(value)}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                text_parts.append(f"{indent}[{i}]")
                if isinstance(item, (dict, list)):
                    self._extract_hjson_text(item, text_parts, depth + 1)
                else:
                    text_parts.append(f"{indent}  {str(item)}")

    def chunk_text(self, text):
        # Simple whitespace tokenizer for chunking
        tokens = text.split()
        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk = " ".join(tokens[start:end])
            chunks.append(chunk)
            if end == len(tokens):
                break
            start += self.chunk_size - self.chunk_overlap
        return chunks

    def chunk_files(self):
        print(f"Scanning for documents in corpus paths: {', '.join(str(p) for p in self.corpus_paths)}")
        file_count = 0

        for corpus_path in self.corpus_paths:
            if corpus_path.is_dir():
                for root, _, files in os.walk(corpus_path):
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        file_count += self._ingest_file(file_path)
            elif corpus_path.is_file():
                file_count += self._ingest_file(corpus_path)

        print(f"Processed {file_count} files, created {len(self.all_chunks)} chunks")

    def create_index(self):
        if not self.all_chunks:
            print("No chunks found. Scanning corpus...")
            self.chunk_files()

        if not self.all_chunks:
            raise ValueError("No documents found in corpus. Please add PDF/MD/TXT/SV/SVH/V/VH/HJSON files to the corpus directory.")

        print(f"\n{'='*80}")
        print(f"Creating embeddings for {len(self.all_chunks)} chunks...")
        print(f"Device: {self.device} | Batch size: {self.batch_size} | Workers: {self.num_workers}")
        print(f"{'='*80}\n")

        try:
            # Optimize encoding parameters
            encode_kwargs = {
                'batch_size': self.batch_size,
                'show_progress_bar': True,
                'convert_to_numpy': True
            }

            # Add multi-processing for CPU
            if self.device == 'cpu':
                encode_kwargs['multi_process'] = True
                encode_kwargs['num_workers'] = self.num_workers

            embeddings = self.model.encode(self.all_chunks, **encode_kwargs)

        except Exception as e:
            raise RuntimeError(f"Failed to create embeddings: {e}")

        dim = embeddings.shape[1]
        print(f"\nBuilding FAISS index (dimension: {dim})...")
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(embeddings.astype(np.float32))
        print(f"Index created successfully with {self.index.ntotal} vectors\n")

    def retrieve_relevant_chunks(self, query, top_k=5):
        print(f"Retrieving chunks for query: '{query[:100]}...'")
        if self.index is None:
            print("Index not found. Creating new index...")
            self.create_index()

        if self.index.ntotal == 0:
            print("Warning: Index is empty")
            return []

        try:
            # Encode query and ensure it's on CPU as numpy array
            query_embedding = self.model.encode([query], convert_to_numpy=True)

            # Ensure numpy array format
            if not isinstance(query_embedding, np.ndarray):
                query_embedding = np.array(query_embedding)

            # Reshape if needed (FAISS expects 2D array)
            if query_embedding.ndim == 1:
                query_embedding = query_embedding.reshape(1, -1)

            distances, indices = self.index.search(query_embedding.astype(np.float32), top_k)
            results = [(self.all_chunks[i], self.file_paths[i], distances[0][j]) for j, i in enumerate(indices[0])]
            print(f"Retrieved {len(results)} chunks")
            return results
        except Exception as e:
            print(f"Error during retrieval: {e}")
            return []

    def add_texts(self, texts, source: str = "runtime", persist: bool = False, index_name: str | None = None):
        """
        Add raw text snippets to the vector store at runtime.

        Args:
            texts: A string or list of strings to add.
            source: Identifier for where the text came from (stored with each chunk).
            persist: If True, save the index after updating.
            index_name: Optional override for save name (defaults to self.index_name).
        """
        if isinstance(texts, str):
            texts = [texts]

        new_chunks = []
        for text in texts:
            if not text:
                continue
            for chunk in self.chunk_text(text):
                if chunk.strip():
                    new_chunks.append(chunk)

        if not new_chunks:
            print("No new chunks to add to the vector store.")
            return

        try:
            encode_kwargs = {
                'batch_size': self.batch_size,
                'show_progress_bar': False,
                'convert_to_numpy': True
            }
            if self.device == 'cpu':
                encode_kwargs['multi_process'] = True
                encode_kwargs['num_workers'] = self.num_workers

            embeddings = self.model.encode(new_chunks, **encode_kwargs)
        except Exception as e:
            print(f"Failed to encode new chunks: {e}")
            return

        # Ensure embeddings is a NumPy array with dtype float32
        embeddings = np.asarray(embeddings, dtype=np.float32)

        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)

        # Initialize index if it doesn't exist
        if self.index is None:
            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dim)

        self.index.add(embeddings)
        self.all_chunks.extend(new_chunks)
        self.file_paths.extend([source] * len(new_chunks))

        if persist:
            save_name = index_name or self.index_name or "default"
            self.save_index(name=save_name)

    def save_index(self, name="default"):
        if self.index is None:
            raise ValueError("No index to save. Create index first with create_index()")

        self.index_name = name

        save_dir = self.index_path / name
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        index_file = save_dir / "faiss.index"
        faiss.write_index(self.index, str(index_file))
        print(f"Saved FAISS index to {index_file}")

        # Save metadata (chunks, file paths)
        metadata = {
            'all_chunks': self.all_chunks,
            'file_paths': self.file_paths,
            'chunk_size': self.chunk_size,
            'chunk_overlap': self.chunk_overlap,
            'directory': str(self.directory),
            'corpus_paths': [str(p) for p in self.corpus_paths],
            'saved_at': datetime.now().isoformat()
        }
        metadata_file = save_dir / "metadata.pkl"
        with open(metadata_file, 'wb') as f:
            pickle.dump(metadata, f)
        print(f"Saved metadata to {metadata_file}")

        # Save summary stats
        stats = self.get_stats()
        stats_file = save_dir / "stats.txt"
        with open(stats_file, 'w') as f:
            f.write(stats)
        print(f"Saved statistics to {stats_file}")

        print(f"Index '{name}' saved successfully!")

    def load_index(self, name="default"):
        load_dir = self.index_path / name

        if not load_dir.exists():
            print(f"No saved index found at {load_dir}")
            return False
        self.index_name = name

        try:
            # Load FAISS index
            index_file = load_dir / "faiss.index"
            if not index_file.exists():
                print(f"Index file not found: {index_file}")
                return False

            self.index = faiss.read_index(str(index_file))
            print(f"Loaded FAISS index from {index_file} ({self.index.ntotal} vectors)")

            # Load metadata
            metadata_file = load_dir / "metadata.pkl"
            if not metadata_file.exists():
                print(f"Metadata file not found: {metadata_file}")
                return False

            with open(metadata_file, 'rb') as f:
                metadata = pickle.load(f)

            self.all_chunks = metadata['all_chunks']
            self.file_paths = metadata['file_paths']
            self.chunk_size = metadata.get('chunk_size', self.chunk_size)
            self.chunk_overlap = metadata.get('chunk_overlap', self.chunk_overlap)
            loaded_corpus = metadata.get('corpus_paths')
            if loaded_corpus:
                self.corpus_paths = [Path(p) for p in loaded_corpus]

            saved_at = metadata.get('saved_at', 'unknown')
            print(f"Loaded metadata (saved at: {saved_at})")
            print(f"Index '{name}' loaded successfully!")
            return True

        except Exception as e:
            print(f"Error loading index: {e}")
            return False

    def get_stats(self):
        stats = []
        stats.append("=" * 60)
        stats.append("VECTOR STORE STATISTICS")
        stats.append("=" * 60)

        # Corpus info
        stats.append(f"Corpus Directory: {self.directory}")
        stats.append(f"Corpus Paths: {[str(p) for p in self.corpus_paths]}")
        stats.append(f"Index Path: {self.index_path}")

        # Chunk info
        stats.append(f"\nChunking Configuration:")
        stats.append(f"  Chunk Size: {self.chunk_size} tokens")
        stats.append(f"  Chunk Overlap: {self.chunk_overlap} tokens")
        stats.append(f"  Total Chunks: {len(self.all_chunks)}")

        # Index info
        if self.index is not None:
            stats.append(f"\nFAISS Index:")
            stats.append(f"  Vectors: {self.index.ntotal}")
            stats.append(f"  Dimension: {self.index.d}")
        else:
            stats.append(f"\nFAISS Index: Not created")

        # File info
        if self.file_paths:
            unique_files = len(set(self.file_paths))
            stats.append(f"\nDocuments:")
            stats.append(f"  Unique Files: {unique_files}")
            stats.append(f"  Total Chunks: {len(self.file_paths)}")

            # Count by file type
            pdf_count = sum(1 for p in set(self.file_paths) if p.lower().endswith('.pdf'))
            md_count = sum(1 for p in set(self.file_paths) if p.lower().endswith('.md'))
            txt_count = sum(1 for p in set(self.file_paths) if p.lower().endswith('.txt'))
            sv_count = sum(1 for p in set(self.file_paths) if p.lower().endswith(('.sv', '.svh', '.v', '.vh')))
            hjson_count = sum(1 for p in set(self.file_paths) if p.lower().endswith('.hjson'))

            stats.append(f"  PDF Files: {pdf_count}")
            stats.append(f"  Markdown Files: {md_count}")
            stats.append(f"  Text Files: {txt_count}")
            stats.append(f"  Verilog/SystemVerilog Files: {sv_count}")
            stats.append(f"  HJSON Files: {hjson_count}")

            # Most common files
            from collections import Counter
            file_counter = Counter(self.file_paths)
            stats.append(f"\nTop 5 Most Chunked Files:")
            for file_path, count in file_counter.most_common(5):
                filename = os.path.basename(file_path)
                stats.append(f"  {filename}: {count} chunks")

        stats.append("=" * 60)
        return "\n".join(stats)
