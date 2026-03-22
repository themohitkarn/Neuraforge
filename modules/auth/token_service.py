# modules/auth/token_service.py
# Token system for NeuraForge — tracks usage and enforces limits

import logging
from database import db
from database.models.user import User

logger = logging.getLogger(__name__)

# Token costs per action
TOKEN_COSTS = {
    "generate_website": {"user": 10, "premium": 5, "admin": 0},
    "regenerate_section": {"user": 3, "premium": 1, "admin": 0},
    "chat_message": {"user": 1, "premium": 0, "admin": 0},
    "export_website": {"user": 2, "premium": 0, "admin": 0},
    "upload_website": {"user": 5, "premium": 2, "admin": 0},
}


class TokenService:

    @staticmethod
    def get_cost(user: User, action: str) -> int:
        """Get the token cost for an action based on user's role."""
        costs = TOKEN_COSTS.get(action, {"user": 1, "premium": 0, "admin": 0})
        if user.is_admin:
            return 0
        return costs.get(user.role, costs.get("user", 1))

    @staticmethod
    def can_afford(user_id: int, action: str) -> tuple:
        """Check if user can afford an action. Returns (can_afford, cost, balance)."""
        user = User.query.get(user_id)
        if not user:
            return False, 0, 0

        cost = TokenService.get_cost(user, action)

        if cost == 0:
            return True, 0, user.tokens

        if user.tokens >= cost:
            return True, cost, user.tokens
        else:
            return False, cost, user.tokens

    @staticmethod
    def deduct(user_id: int, action: str) -> tuple:
        """Deduct tokens for an action. Returns (success, message)."""
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"

        cost = TokenService.get_cost(user, action)

        if cost == 0:
            return True, "No charge (premium/admin)"

        if user.tokens >= cost:
            user.tokens -= cost
            db.session.commit()
            logger.info(f"Deducted {cost} tokens from user {user_id} for {action}. Balance: {user.tokens}")
            return True, f"Deducted {cost} tokens. Balance: {user.tokens}"
        else:
            return False, f"Insufficient tokens. Need {cost}, have {user.tokens}. Upgrade to Premium for more!"

    @staticmethod
    def grant_tokens(user_id: int, amount: int) -> tuple:
        """Grant tokens to a user (admin action)."""
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"

        user.tokens += amount
        db.session.commit()
        return True, f"Granted {amount} tokens. New balance: {user.tokens}"

    @staticmethod
    def get_info(user_id: int) -> dict:
        """Get token info for display."""
        user = User.query.get(user_id)
        if not user:
            return {}

        return {
            "balance": user.tokens,
            "role": user.role,
            "is_admin": user.is_admin,
            "is_premium": user.is_premium,
            "display": user.token_display,
            "costs": {
                action: TokenService.get_cost(user, action)
                for action in TOKEN_COSTS
            }
        }
