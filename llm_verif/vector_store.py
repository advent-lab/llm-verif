import os
import fitz  # PyMuPDF
import pdfplumber
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# Initialize the embedding model
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

# Function to extract tables from PDF
def extract_tables_from_pdf(pdf_path):
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables += page.extract_tables()
    return tables

# Function to extract graphic captions from PDF (if applicable)
def extract_graphics_captions(pdf_path):
    captions = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            # Extract images and their descriptions or captions
            for img_index, img in enumerate(page.get_images(full=True)):
                # Get image info (for example)
                caption = f"Graphic {img_index + 1}: Image found on page {page.number + 1}"
                captions.append(caption)
    return captions

# Function to read and process Markdown and text files
def read_text_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

# Function to create vector embeddings and store them in FAISS
def create_vector_store(directory):
    all_chunks = []
    all_embeddings = []

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)

        if filename.endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
            all_chunks.append(text)

            # Extract tables
            tables = extract_tables_from_pdf(file_path)
            for table in tables:
                # Format the table as a string for embedding
                table_str = "\n".join(["\t".join(map(str, row)) for row in table])
                all_chunks.append(f"Table:\n{table_str}")

            # Extract graphic captions
            captions = extract_graphics_captions(file_path)
            for caption in captions:
                all_chunks.append(caption)

        elif filename.endswith('.md') or filename.endswith('.txt'):
            text = read_text_file(file_path)
            all_chunks.append(text)

    # Create embeddings for all chunks
    embeddings = model.encode(all_chunks, convert_to_tensor=True).numpy()

    # Create a FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    return index, all_chunks

# Function to retrieve relevant chunks based on a query
def retrieve_relevant_chunks(query, index, all_chunks, top_k=5):
    query_embedding = model.encode([query], convert_to_tensor=True).numpy()
    distances, indices = index.search(np.array(query_embedding), top_k)
    return [(all_chunks[i], distances[0][j]) for j, i in enumerate(indices[0])]

# Main workflow
directory = '/home/slowe8/Research/llm_verif_dataset/data_points/agalimberti_NoCRouter_router/doc'  # Update this path
index, all_chunks = create_vector_store(directory)

# Example query to retrieve relevant chunks
query = "Describe the RTL Router Design"
relevant_chunks = retrieve_relevant_chunks(query, index, all_chunks)

# Print the relevant chunks and their distances
for chunk, distance in relevant_chunks:
    print(f"Chunk: {chunk}\nDistance: {distance}\n")
