# modules/ai_generator/design_memory.py
# Anti-duplication system: stores output hashes and prevents repeated designs

import hashlib
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class DesignMemory:
    """
    In-memory design output tracker per user.
    Stores MD5 hashes of generated outputs to detect and prevent duplicates.
    """
    
    MAX_MEMORY_PER_USER = 20
    
    def __init__(self):
        self._memory = defaultdict(list)  # user_id -> [hash1, hash2, ...]
    
    @staticmethod
    def compute_hash(output_text: str) -> str:
        """Compute MD5 hash of the generated output."""
        return hashlib.md5(output_text.encode('utf-8')).hexdigest()
    
    def is_duplicate(self, user_id: int, output_text: str) -> bool:
        """Check if this output was already generated for this user."""
        output_hash = self.compute_hash(output_text)
        return output_hash in self._memory.get(user_id, [])
    
    def store(self, user_id: int, output_text: str) -> str:
        """Store the hash of a generated output. Returns the hash."""
        output_hash = self.compute_hash(output_text)
        user_hashes = self._memory[user_id]
        
        if output_hash not in user_hashes:
            user_hashes.append(output_hash)
            # Keep only the last N
            if len(user_hashes) > self.MAX_MEMORY_PER_USER:
                self._memory[user_id] = user_hashes[-self.MAX_MEMORY_PER_USER:]
        
        logger.info(f"Stored design hash for user {user_id}. Memory size: {len(self._memory[user_id])}")
        return output_hash
    
    def get_memory_size(self, user_id: int) -> int:
        return len(self._memory.get(user_id, []))
    
    def clear(self, user_id: int):
        """Clear design memory for a user."""
        self._memory.pop(user_id, None)


# Singleton instance
design_memory = DesignMemory()
