from opengeo.readability import count_syllables, definition_paragraph_ratio, readability_metrics


def test_syllable_counter_handles_common_words():
    assert count_syllables("table") == 2
    assert count_syllables("language") == 2
    assert count_syllables("the") == 1
    assert count_syllables("development") == 3
    assert count_syllables("programming") == 3
    assert count_syllables("level") == 2


def test_readability_metrics_shape_and_range():
    text = ("Python is a high-level programming language. It is easy to read. "
            "Many developers like it. The syntax is plain and readable. "
            "Most teams use Python daily for automation work.")
    m = readability_metrics(text)
    # 'high-level' is split at the hyphen by the word regex, so 30 tokens.
    assert m["word_count"] == 30
    assert m["sentence_count"] >= 4
    assert 0 <= m["flesch_reading_ease"] <= 100
    assert m["flesch_kincaid_grade"] > 0
    assert m["dale_chall_difficulty"] > 0
    assert m["reading_level"]


def test_readability_metrics_empty_text():
    m = readability_metrics("")
    assert m["word_count"] == 0
    assert m["flesch_reading_ease"] is None
    assert m["reading_level"] == "no readable text"


def test_definition_paragraph_ratio_detects_definition_style():
    paras = [
        "Python is a high-level, general-purpose programming language.",
        "It refers to a suite of tools that automate repetitive tasks.",
        "Random prose that is much longer than forty words and therefore does not qualify "
        "as a definition-style paragraph at all so the ratio stays low.",
    ]
    ratio = definition_paragraph_ratio(paras)
    assert 0 < ratio <= 1
    assert ratio >= 0.5  # at least two of three are definition-shaped
