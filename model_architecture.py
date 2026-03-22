import torch
import torch.nn as nn
import torch.nn.functional as F
import math

class PositionalEncoding(nn.Module):
    """
    Injects positional information into the tokens since Transformers 
    have no inherent sense of order (unlike RNNs).
    """
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        # Create a matrix of [max_len, d_model]
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        # Calculate the frequencies for the positional encoding
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        
        # Apply sin to even indices and cos to odd indices
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        
        # Add a batch dimension [1, max_len, d_model]
        pe = pe.unsqueeze(0)
        # Register as a buffer so it saves with the model but isn't a trainable parameter
        self.register_buffer('pe', pe)

    def forward(self, x):
        """
        x is the token embeddings [batch_size, seq_len, d_model]
        """
        # Add the positional encoding up to the current sequence length
        x = x + self.pe[:, :x.size(1)]
        return x

class TemplateGeneratorModel(nn.Module):
    """
    A custom Transformer-based model designed to generate HTML, CSS, and JS 
    structures based on our scraped dataset.
    """
    def __init__(self, vocab_size, d_model=256, nhead=8, num_layers=4, dim_feedforward=1024, dropout=0.1, max_seq_length=4096):
        super().__init__()
        self.d_model = d_model
        
        # 1. Embedding Layer: Converts token IDs to dense vectors of size d_model
        self.embedding = nn.Embedding(num_embeddings=vocab_size, embedding_dim=d_model)
        
        # 2. Positional Encoding
        self.pos_encoder = PositionalEncoding(d_model=d_model, max_len=max_seq_length)
        
        # 3. Transformer Decoder (We use Decoder-only setup like GPT for generation)
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=d_model, 
            nhead=nhead, 
            dim_feedforward=dim_feedforward, 
            dropout=dropout,
            batch_first=True  # Important: ensures [batch, seq, feature] shape
        )
        self.transformer_decoder = nn.TransformerDecoder(decoder_layer, num_layers=num_layers)
        
        # 4. Output Layer to project back to vocabulary size
        self.fc_out = nn.Linear(d_model, vocab_size)
        
        # Apply dropout to embeddings too
        self.dropout = nn.Dropout(dropout)

    def generate_square_subsequent_mask(self, sz):
        """
        Generates a causal mask so the model can't "look ahead" into the future tokens during training.
        """
        mask = (torch.triu(torch.ones(sz, sz)) == 1).transpose(0, 1)
        mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))
        return mask

    def forward(self, x, memory=None):
        """
        x: Input token IDs [batch_size, seq_len]
        memory: Optional context/prompt encoded by an encoder (if we switch to seq2seq)
        """
        seq_len = x.size(1)
        
        # Create causality mask
        tgt_mask = self.generate_square_subsequent_mask(seq_len).to(x.device)
        
        # Embed tokens and scale, then add position info
        x = self.embedding(x) * math.sqrt(self.d_model)
        x = self.pos_encoder(x)
        x = self.dropout(x)
        
        # If we are doing purely autoregressive (GPT style), we can pass a dummy memory
        # or use encoder-decoder. For simplicity now, we mock memory to itself.
        if memory is None:
             memory = torch.zeros_like(x)
             
        # Pass through Transformer Decoder layers
        output = self.transformer_decoder(
            tgt=x, 
            memory=memory, 
            tgt_mask=tgt_mask
        )
        
        # Project back to vocabulary logits
        logits = self.fc_out(output)
        return logits

def test_model_initialization():
    """Simple test to verify model instantiates and can run a forward pass."""
    print("Testing TemplateGeneratorModel Initialization...")
    
    # Mock parameters
    vocab_size = 5000  # Will depend on our HTML/CSS/JS tokenizer later
    batch_size = 2
    seq_length = 256
    
    model = TemplateGeneratorModel(vocab_size=vocab_size, d_model=128, nhead=4, num_layers=2)
    
    # Create fake batch of token IDs
    dummy_input = torch.randint(0, vocab_size, (batch_size, seq_length))
    
    print(f"Dummy Input shape: {dummy_input.shape} [batch_size, seq_length]")
    
    # Run a forward pass
    logits = model(dummy_input)
    
    print(f"Logits Output shape: {logits.shape} [batch_size, seq_length, vocab_size]")
    print("✅ Model architecture is sound and ready for the training loop.")

if __name__ == "__main__":
    test_model_initialization()
