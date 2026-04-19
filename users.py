import hashlib

# ── USER DATABASE ──────────────────────────────────────────
# In production this would be a real database
# For learning — a simple dictionary
# Passwords stored as SHA256 hashes — never plain text

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

USERS = {
    "operator1": {
        "password": hash_password("op123"),
        "role": "operator",
        "full_name": "Plant Operator"
    },
    "engineer1": {
        "password": hash_password("eng123"),
        "role": "engineer",
        "full_name": "Plant Engineer"
    },
    "admin": {
        "password": hash_password("admin123"),
        "role": "engineer",
        "full_name": "Plant Admin"
    }
}

def verify_user(username, password):
    """
    Check if username and password are correct
    Returns user dict if valid, None if invalid
    """
    if username not in USERS:
        return None

    user = USERS[username]
    if user["password"] == hash_password(password):
        return {
            "username": username,
            "role": user["role"],
            "full_name": user["full_name"]
        }
    return None

def get_role(username):
    """Get role for a username"""
    if username in USERS:
        return USERS[username]["role"]
    return None