import os
import time
import json
import base64
import hmac
import hashlib
from typing import Optional, Dict, Any, Tuple

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-jwt-agent-rag-key-2026")
JWT_ALGORITHM = "HS256"

# Pure Python base64url helpers
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def _b64url_decode(data_str: str) -> bytes:
    padding = "=" * ((4 - len(data_str) % 4) % 4)
    return base64.urlsafe_b64decode(data_str + padding)

def get_domain_from_email(email: Optional[str]) -> Optional[str]:
    """Extract domain from an email address. Returns None if no @ exists (e.g. 'admin')."""
    if not email or "@" not in email:
        return None
    parts = email.split("@")
    domain = parts[-1].strip().lower()
    return domain if domain else None

def generate_jwt_token(email: str, role: str = "User", domain: Optional[str] = None, expires_in_seconds: int = 86400, secret: str = JWT_SECRET) -> str:
    """Generate a signed JWT token containing email, role, and domain."""
    if domain is None:
        domain = get_domain_from_email(email)

    now = int(time.time())
    payload = {
        "sub": email,
        "email": email,
        "role": role,
        "domain": domain,
        "iat": now,
        "exp": now + expires_in_seconds
    }

    # Try standard PyJWT if available
    try:
        import jwt
        token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token
    except Exception:
        # Fallback pure-Python HS256 JWT implementation
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        sig_b64 = _b64url_encode(sig)
        return f"{header_b64}.{payload_b64}.{sig_b64}"

def decode_jwt_token(token: str, secret: str = JWT_SECRET) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT token. Returns payload dict or None if invalid/expired."""
    if not token:
        return None

    clean_token = token.strip()
    if clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip()

    # Try PyJWT
    try:
        import jwt
        payload = jwt.decode(clean_token, secret, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        pass

    # Pure Python fallback verification
    try:
        parts = clean_token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Verify expiration
        exp = payload.get("exp")
        if exp and int(exp) < int(time.time()):
            return None

        return payload
    except Exception:
        return None

def extract_jwt_from_request(req) -> Optional[str]:
    """Extract JWT token from Flask request headers, query args, or json body."""
    auth_header = req.headers.get("Authorization")
    if auth_header and "bearer " in auth_header.lower():
        return auth_header.split(None, 1)[1].strip()

    for h in ["X-JWT-Token", "X-API-Key", "X-Token"]:
        val = req.headers.get(h)
        if val and val.strip():
            return val.strip()

    if req.args:
        for p in ["token", "jwt_token", "api_key"]:
            val = req.args.get(p)
            if val and val.strip():
                return val.strip()

    data = req.get_json(silent=True)
    if isinstance(data, dict):
        for p in ["jwt_token", "token", "api_key"]:
            val = data.get(p)
            if val and isinstance(val, str) and val.strip():
                return val.strip()

    return None

def authenticate_request(req, secret: str = JWT_SECRET) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Validate request using JWT token.
    Returns (is_valid, payload, error_or_status_message).
    """
    token = extract_jwt_from_request(req)
    if not token:
        # Development fallback: check if master key
        return False, None, "Missing authentication token"

    payload = decode_jwt_token(token, secret=secret)
    if not payload:
        return False, None, "Invalid or expired JWT token"

    return True, payload, "Valid"
