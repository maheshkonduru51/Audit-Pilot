from app.memory.long_term import get_preferences, store_preference
from seed import seed

def test_preference_memory():
    seed()
    store_preference(1, "show INR in lakhs")
    assert "show INR in lakhs" in get_preferences(1)
