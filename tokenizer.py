import json
import torch
import collections

class TemplateTokenizer:
    """
    A simple character/word-level tokenizer specifically designed to break down
    our JSON dataset containing HTML, CSS, and JS.
    For a production model, you would use Subword tokenization (BPE/WordPiece) 
    like the `tokenizers` library from Hugging Face, but we are building from scratch!
    """
    def __init__(self):
        self.vocab = {"<PAD>": 0, "<UNK>": 1, "<BOS>": 2, "<EOS>": 3}
        self.inverse_vocab = {0: "<PAD>", 1: "<UNK>", 2: "<BOS>", 3: "<EOS>"}
        self.vocab_size = 4
        
    def fit_on_dataset(self, dataset_path):
        """
        Reads the scraped dataset and builds a vocabulary from the characters/words.
        For HTML/CSS code, a character-level or symbol-level split is easiest natively.
        Here we will do a simple split by whitespace and common symbols.
        """
        print(f"Building vocabulary from {dataset_path}...")
        
        with open(dataset_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Convert the complex JSON structures into giant strings
        corpus = ""
        for item in data:
            corpus += json.dumps(item["content"], separators=(',', ':')) + " "
            
        # Very rudimentary tokenization: splitting by common syntax boundaries
        # In reality, keeping things character-level or using BPE is better for code
        # We'll use character-level for maximum flexibility on syntax!
        
        chars = sorted(list(set(corpus)))
        for char in chars:
            if char not in self.vocab:
                self.vocab[char] = self.vocab_size
                self.inverse_vocab[self.vocab_size] = char
                self.vocab_size += 1
                
        print(f"Vocabulary built! Size: {self.vocab_size} unique characters/tokens.")
        
    def encode(self, text, max_length=1024):
        """
        Converts a string of HTML/JSON into a PyTorch tensor of token IDs.
        """
        tokens = [self.vocab["<BOS>"]]
        
        for char in text:
            tokens.append(self.vocab.get(char, self.vocab["<UNK>"]))
            
        # Truncate if too long (reserving 1 spot for EOS)
        if len(tokens) > max_length - 1:
            tokens = tokens[:max_length-1]
            
        tokens.append(self.vocab["<EOS>"])
        
        # Pad if too short
        while len(tokens) < max_length:
            tokens.append(self.vocab["<PAD>"])
            
        return torch.tensor(tokens, dtype=torch.long)

    def decode(self, token_ids):
        """
        Converts a list/tensor of token IDs back into an HTML/JSON string.
        """
        if isinstance(token_ids, torch.Tensor):
            token_ids = token_ids.tolist()
            
        text = ""
        for token in token_ids:
            if token in (self.vocab.get("<PAD>"), self.vocab.get("<BOS>"), self.vocab.get("<EOS>")):
                continue
            text += self.inverse_vocab.get(token, "?")
            
        return text

if __name__ == "__main__":
    # Test the tokenizer
    tokenizer = TemplateTokenizer()
    dataset_path = r"d:\NEURAFORGE\html_dataset.json"
    
    tokenizer.fit_on_dataset(dataset_path)
    
    sample_text = '{"tag":"div","attributes":{"class":["hero"]}}'
    encoded = tokenizer.encode(sample_text, max_length=50)
    
    print("\nSample Encoding Test:")
    print(f"Original : {sample_text}")
    print(f"Encoded  : {encoded.tolist()}")
    print(f"Decoded  : {tokenizer.decode(encoded)}")
