from app.api.auth import create_token, decode_token

def test_token_round_trip():
    token = create_token(1, "analyst@jnmv.com", "analyst")
    payload = decode_token(token)
    assert payload["sub"] == "1" and payload["role"] == "analyst"

def test_token_contains_email():
    token = create_token(2, "manager@jnmv.com", "manager")
    assert decode_token(token)["email"] == "manager@jnmv.com"
