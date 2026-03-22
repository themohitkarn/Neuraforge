import ast
import faiss
import numpy as np
from typing import List, Dict, Any
from core.project_analyzer import scan_project
from vector_store.embeddings import EmbeddingsModel

class CodeChunker:
    """Chunks code strings into AST nodes like classes and functions."""
    
    @staticmethod
    def chunk_python_code(code: str, file_path: str) -> List[Dict[str, Any]]:
        chunks = []
        try:
            tree = ast.parse(code)
            lines = code.split('\n')
            
            # Extract classes and functions
            for node in tree.body:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    start_lineno = node.lineno - 1
                    end_lineno = node.end_lineno if hasattr(node, "end_lineno") else len(lines)
                    
                    chunk_code = '\n'.join(lines[start_lineno:end_lineno])
                    chunks.append({
                        "file_path": file_path,
                        "type": type(node).__name__,
                        "name": node.name,
                        "content": chunk_code
                    })
            
            # If no classes or functions, or it's a small file, just chunk the whole thing
            if not chunks:
                chunks.append({
                    "file_path": file_path,
                    "type": "Module",
                    "name": "Global",
                    "content": code
                })
        except SyntaxError:
            # Fallback for invalid python code
            chunks.append({
                "file_path": file_path,
                "type": "Raw",
                "name": "Fallback",
                "content": code
            })
        return chunks

    @staticmethod
    def chunk_generic_text(text: str, file_path: str, chunk_size=500) -> List[Dict[str, Any]]:
        """Simple line-based chunker for non-python files."""
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_len = 0
        
        for i, line in enumerate(lines):
            current_chunk.append(line)
            current_len += len(line)
            
            if current_len >= chunk_size or i == len(lines) - 1:
                chunks.append({
                    "file_path": file_path,
                    "type": "TextChunk",
                    "name": f"Lines {i - len(current_chunk) + 1}-{i}",
                    "content": '\n'.join(current_chunk)
                })
                current_chunk = []
                current_len = 0
                
        if not chunks:
            chunks.append({
                "file_path": file_path,
                "type": "Empty",
                "name": "Empty",
                "content": ""
            })
        return chunks

class VectorIndex:
    def __init__(self):
        self.model = EmbeddingsModel()
        self.index = None
        self.chunk_metadata = []
        
    def build_index(self):
        """Scans the project, chunks the files, and builds the FAISS index."""
        files = scan_project()
        all_chunks = []
        
        for f in files:
            path = f['path']
            content = f['content']
            
            if path.endswith('.py'):
                all_chunks.extend(CodeChunker.chunk_python_code(content, path))
            else:
                all_chunks.extend(CodeChunker.chunk_generic_text(content, path))
                
        if not all_chunks:
            return
            
        self.chunk_metadata = all_chunks
        texts_to_embed = [
            f"File: {c['file_path']} | Type: {c['type']} | Name: {c['name']}\n{c['content']}" 
            for c in all_chunks
        ]
        
        embeddings = self.model.get_embeddings(texts_to_embed)
        
        # Initialize FAISS index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves the most relevant code sections for the given query.
        """
        if self.index is None or self.index.ntotal == 0:
            self.build_index()
            # If still empty after building
            if self.index is None or self.index.ntotal == 0:
                return []
                
        query_embedding = self.model.get_embedding(query).reshape(1, -1)
        k = min(top_k, self.index.ntotal)
        
        distances, indices = self.index.search(query_embedding, k)
        
        results = []
        for i in indices[0]:
            if i != -1 and i < len(self.chunk_metadata):
                results.append(self.chunk_metadata[i])
                
        return results
