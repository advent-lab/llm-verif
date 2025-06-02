import os
import fitz  # PyMuPDF
import pdfplumber
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

class VectorStore:
    def __init__(self, directory, chunk_size=256, chunk_overlap=32):
        print("Initializing VectorStore...")
        self.directory = directory
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self.all_chunks = []
        self.file_paths = []
        self.index = None
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_text_from_pdf(self, pdf_path):
        text = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text()
        return text

    def extract_tables_from_pdf(self, pdf_path):
        tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables += page.extract_tables()
        return tables

    def extract_graphics_captions(self, pdf_path):
        captions = []
        with fitz.open(pdf_path) as doc:
            for page in doc:
                for img_index, img in enumerate(page.get_images(full=True)):
                    caption = f"Graphic {img_index + 1}: Image found on page {page.number + 1}"
                    captions.append(caption)
        return captions

    def read_text_file(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

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
        for root, _, files in os.walk(self.directory):
            for filename in files:
                file_path = os.path.join(root, filename)
                if filename.lower().endswith('.pdf'):
                    text = self.extract_text_from_pdf(file_path)
                    for chunk in self.chunk_text(text):
                        self.all_chunks.append(chunk)
                        self.file_paths.append(file_path)

                    tables = self.extract_tables_from_pdf(file_path)
                    for table in tables:
                        table_str = "\n".join(["\t".join(map(str, row)) for row in table])
                        for chunk in self.chunk_text(f"Table:\n{table_str}"):
                            self.all_chunks.append(chunk)
                            self.file_paths.append(file_path)

                    captions = self.extract_graphics_captions(file_path)
                    for caption in captions:
                        for chunk in self.chunk_text(caption):
                            self.all_chunks.append(chunk)
                            self.file_paths.append(file_path)

                elif filename.lower().endswith('.md') or filename.lower().endswith('.txt'):
                    text = self.read_text_file(file_path)
                    for chunk in self.chunk_text(text):
                        self.all_chunks.append(chunk)
                        self.file_paths.append(file_path)

    def create_index(self):
        if not self.all_chunks:
            self.chunk_files()
        embeddings = self.model.encode(self.all_chunks, convert_to_tensor=True).numpy()
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(embeddings)

    def retrieve_relevant_chunks(self, query, top_k=5):
        print(f"Retrieving chunks for query:\n{query}")
        if self.index is None:
            self.create_index()
        query_embedding = self.model.encode([query], convert_to_tensor=True).numpy()
        distances, indices = self.index.search(np.array(query_embedding), top_k)
        return [(self.all_chunks[i], self.file_paths[i], distances[0][j]) for j, i in enumerate(indices[0])]
