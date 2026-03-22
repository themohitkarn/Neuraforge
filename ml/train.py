import json
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import Dataset, DataLoader
from tokenizer import TemplateTokenizer
from model_architecture import TemplateGeneratorModel

# Enable cudnn auto-tuner
torch.backends.cudnn.benchmark = True


class TemplateDataset(Dataset):
    """Loads JSON and creates overlapping token chunks."""
    def __init__(self, json_path, tokenizer, max_length=512, stride=256):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.stride = stride
        self.chunks = []

        print(f"Loading dataset from {json_path}...")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data:
            text_representation = json.dumps(item["content"], separators=(',', ':'))

            tokens = [self.tokenizer.vocab["<BOS>"]]
            for char in text_representation:
                tokens.append(
                    self.tokenizer.vocab.get(char, self.tokenizer.vocab["<UNK>"])
                )
            tokens.append(self.tokenizer.vocab["<EOS>"])

            for i in range(0, max(1, len(tokens) - max_length + 2), stride):
                chunk = tokens[i:i + max_length]

                while len(chunk) < max_length:
                    chunk.append(self.tokenizer.vocab["<PAD>"])

                self.chunks.append(torch.tensor(chunk, dtype=torch.long))

        print(f"Loaded {len(data)} templates")
        print(f"Created {len(self.chunks)} training sequences")

    def __len__(self):
        return len(self.chunks)

    def __getitem__(self, idx):
        tokens = self.chunks[idx]
        x = tokens[:-1]
        y = tokens[1:]
        return x, y


def train_model():

    # =====================
    # CONFIG
    # =====================
    BATCH_SIZE = 128
    MAX_LENGTH = 512
    EPOCHS = 10
    LEARNING_RATE = 5e-4
    DATASET_PATH = "html_dataset.json"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # =====================
    # TOKENIZER
    # =====================
    tokenizer = TemplateTokenizer()
    tokenizer.fit_on_dataset(DATASET_PATH)
    vocab_size = tokenizer.vocab_size

    # =====================
    # DATASET
    # =====================
    dataset = TemplateDataset(DATASET_PATH, tokenizer, max_length=MAX_LENGTH)

    dataloader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=4,
        pin_memory=True
    )

    # =====================
    # MODEL
    # =====================
    model = TemplateGeneratorModel(
        vocab_size=vocab_size,
        d_model=512,
        nhead=8,
        num_layers=6,
        max_seq_length=MAX_LENGTH
    ).to(device)

    # ADD THIS LINE BACK IN FOR MULTI-GPU:
    model = torch.nn.DataParallel(model)

    print(f"Model parameters: {sum(p.numel() for p in model.parameters())}")

    # =====================
    # OPTIMIZER + LOSS
    # =====================
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE)
    criterion = nn.CrossEntropyLoss(
        ignore_index=tokenizer.vocab["<PAD>"]
    )

    # =====================
    # MIXED PRECISION
    # =====================
    scaler = torch.cuda.amp.GradScaler()

    # =====================
    # TRAINING LOOP
    # =====================
    model.train()
    best_loss = float("inf")

    print("\n===== TRAINING STARTED =====\n")

    for epoch in range(EPOCHS):

        total_loss = 0

        for batch_idx, (x, y) in enumerate(dataloader):

            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            optimizer.zero_grad()

            # Mixed Precision Forward
            with torch.cuda.amp.autocast():
                logits = model(x)
                logits = logits.view(-1, vocab_size)
                y = y.view(-1)
                loss = criterion(logits, y)

            # Backward
            scaler.scale(loss).backward()

            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)

            scaler.step(optimizer)
            scaler.update()

            total_loss += loss.item()

            if batch_idx % 50 == 0:
                print(
                    f"Epoch [{epoch+1}/{EPOCHS}] "
                    f"Batch [{batch_idx+1}/{len(dataloader)}] "
                    f"Loss: {loss.item():.4f}"
                )

        avg_loss = total_loss / len(dataloader)

        print(f"\n==> Epoch {epoch+1} Complete | Avg Loss: {avg_loss:.4f}\n")

        # Save latest
        torch.save(model.state_dict(), "template_generator_model.pth")

        # Save best
        if avg_loss < best_loss:
            best_loss = avg_loss
            torch.save(model.state_dict(), "template_generator_best.pth")
            print("New best model saved!")

    print("\nTraining Finished Successfully!")


if __name__ == "__main__":
    train_model()
