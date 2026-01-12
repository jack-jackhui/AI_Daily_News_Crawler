"""
Threads API Token Manager

Handles automatic token validation, refresh, and expiration detection
for Meta Threads API long-lived access tokens.

Token lifecycle:
- Long-lived tokens are valid for 60 days
- Tokens can be refreshed before expiration to extend validity
- Expired tokens cannot be refreshed (require re-authentication)
"""

import os
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, Tuple
from dotenv import load_dotenv, set_key

load_dotenv()

logger = logging.getLogger(__name__)

# Threads API endpoints
THREADS_DEBUG_TOKEN_URL = "https://graph.threads.net/v1.0/debug_token"
THREADS_REFRESH_TOKEN_URL = "https://graph.threads.net/refresh_access_token"

# Refresh threshold: refresh if token expires within this many days
TOKEN_REFRESH_THRESHOLD_DAYS = 7


def get_token_info(access_token: str) -> Optional[dict]:
    """
    Get metadata about a Threads access token using the debug_token endpoint.

    Args:
        access_token: The Threads access token to inspect

    Returns:
        Token metadata dict with is_valid, expires_at, scopes, etc.
        Returns None if the request fails.
    """
    try:
        response = requests.get(
            THREADS_DEBUG_TOKEN_URL,
            params={
                "access_token": access_token,
                "input_token": access_token
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json().get("data", {})
            return data
        else:
            logger.warning(f"⚠️ Token debug request failed: {response.status_code} - {response.text}")
            return None

    except requests.RequestException as e:
        logger.error(f"❌ Failed to get token info: {e}")
        return None


def check_token_expiration(access_token: str) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Check if a Threads access token is valid and when it expires.

    Args:
        access_token: The Threads access token to check

    Returns:
        Tuple of (is_valid, days_until_expiry, status_message)
        - is_valid: True if token is valid and not expired
        - days_until_expiry: Number of days until token expires (None if invalid)
        - status_message: Human-readable status description
    """
    token_info = get_token_info(access_token)

    if token_info is None:
        return False, None, "Unable to validate token"

    is_valid = token_info.get("is_valid", False)
    expires_at = token_info.get("expires_at")

    if not is_valid:
        return False, None, "Token is invalid or expired"

    if expires_at:
        expiry_date = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        days_remaining = (expiry_date - now).days

        if days_remaining <= 0:
            return False, 0, "Token has expired"
        elif days_remaining <= TOKEN_REFRESH_THRESHOLD_DAYS:
            return True, days_remaining, f"Token expires in {days_remaining} days - refresh recommended"
        else:
            return True, days_remaining, f"Token valid for {days_remaining} more days"

    return is_valid, None, "Token is valid (expiration unknown)"


def refresh_token(access_token: str) -> Optional[str]:
    """
    Refresh a long-lived Threads access token.

    Args:
        access_token: The current valid (unexpired) long-lived token

    Returns:
        New refreshed access token, or None if refresh failed
    """
    try:
        logger.info("🔄 Refreshing Threads access token...")

        response = requests.get(
            THREADS_REFRESH_TOKEN_URL,
            params={
                "grant_type": "th_refresh_token",
                "access_token": access_token
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            new_token = data.get("access_token")
            expires_in = data.get("expires_in", 0)
            expires_days = expires_in // 86400

            logger.info(f"✅ Token refreshed successfully. Valid for {expires_days} days.")
            return new_token
        else:
            logger.error(f"❌ Token refresh failed: {response.status_code} - {response.text}")
            return None

    except requests.RequestException as e:
        logger.error(f"❌ Token refresh request failed: {e}")
        return None


def update_env_token(new_token: str, env_path: str = ".env") -> bool:
    """
    Update the THREADS_ACCESS_TOKEN in the .env file.

    Args:
        new_token: The new access token to save
        env_path: Path to the .env file (default: .env in current directory)

    Returns:
        True if update was successful, False otherwise
    """
    try:
        # Find the .env file - check both project root and src directory
        possible_paths = [
            env_path,
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        ]

        actual_path = None
        for path in possible_paths:
            if os.path.exists(path):
                actual_path = path
                break

        if actual_path is None:
            logger.error("❌ Could not find .env file")
            return False

        set_key(actual_path, "THREADS_ACCESS_TOKEN", new_token)
        logger.info(f"✅ Updated THREADS_ACCESS_TOKEN in {actual_path}")

        # Also update the environment variable in the current process
        os.environ["THREADS_ACCESS_TOKEN"] = new_token

        return True

    except Exception as e:
        logger.error(f"❌ Failed to update .env file: {e}")
        return False


def validate_and_refresh_token(auto_update_env: bool = True) -> Tuple[bool, str, Optional[str]]:
    """
    Main entry point: Validate the current Threads token and refresh if needed.

    This function should be called at pipeline startup to ensure the token
    is valid before attempting to publish.

    Args:
        auto_update_env: If True, automatically update .env with refreshed token

    Returns:
        Tuple of (success, message, current_valid_token)
        - success: True if we have a valid token to use
        - message: Status message describing what happened
        - current_valid_token: The valid token to use (may be refreshed)
    """
    access_token = os.getenv("THREADS_ACCESS_TOKEN")

    if not access_token:
        return False, "THREADS_ACCESS_TOKEN not configured in environment", None

    # Check current token status
    is_valid, days_remaining, status = check_token_expiration(access_token)

    if not is_valid:
        return False, f"❌ Threads token invalid: {status}. Manual re-authentication required.", None

    # Token is valid - check if refresh is recommended
    if days_remaining is not None and days_remaining <= TOKEN_REFRESH_THRESHOLD_DAYS:
        logger.info(f"⚠️ Token expires in {days_remaining} days. Attempting refresh...")

        new_token = refresh_token(access_token)

        if new_token:
            if auto_update_env:
                update_env_token(new_token)
            return True, f"✅ Token refreshed successfully (was expiring in {days_remaining} days)", new_token
        else:
            # Refresh failed but token is still valid
            return True, f"⚠️ Token refresh failed, but current token still valid for {days_remaining} days", access_token

    # Token is valid and not near expiration
    return True, f"✅ Threads token valid ({days_remaining} days remaining)" if days_remaining else "✅ Threads token valid", access_token


if __name__ == "__main__":
    # Test the token manager
    logging.basicConfig(level=logging.INFO)

    print("=" * 50)
    print("Threads Token Manager - Validation Check")
    print("=" * 50)

    success, message, token = validate_and_refresh_token(auto_update_env=False)
    print(f"\nResult: {message}")
    print(f"Success: {success}")
    if token:
        print(f"Token (first 20 chars): {token[:20]}...")
