from src.deduplicate import is_duplicate_title, title_similarity


def test_title_similarity_detects_near_duplicate():
    left = "Federal Reserve leaves interest rates unchanged"
    right = "Fed leaves interest rates unchanged"
    assert title_similarity(left, right) > 0.7


def test_duplicate_title_threshold():
    existing = ["Nvidia shares rise after AI chip demand report"]
    assert is_duplicate_title("Nvidia shares rise after AI chip demand report", existing)
    assert not is_duplicate_title("Oil prices fall as inventory data changes", existing)

