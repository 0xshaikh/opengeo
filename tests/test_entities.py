from opengeo.entities import extract_entities, related_questions, dedupe


def test_entities_keeps_capitalised_multiword_phrases():
    text = ("Microsoft also announced Copilot for enterprise users. "
            "Microsoft said Copilot ships with enterprise controls. "
            "Microsoft confirmed Copilot is available on Windows.")
    ents = extract_entities([text], limit=10, min_count=2)
    assert "Microsoft" in ents
    assert "Copilot" in ents
    assert len(ents) <= 10


def test_entities_keeps_repeated_single_word():
    # A single capitalised word is trusted once it repeats enough.
    text = "Python is fast. Python is portable. Python is dynamic. Python is popular."
    ents = extract_entities([text], limit=10, min_count=1)
    assert "Python" in ents


def test_entities_drops_one_off_snippet_noise():
    # "View" and "Open" are truncation/UI artefacts, not entities.
    ents = extract_entities(["View all results", "Open source python"], min_count=2)
    assert "View" not in ents
    assert "Open" not in ents


def test_entities_strips_prose_with_stopwords():
    ents = extract_entities(["The quick brown fox jumps over the lazy dog"], limit=10)
    # nothing in that sentence is a capitalised named entity
    assert ents == []


def test_related_questions_finds_question_sentences():
    text = "What is Python? Python is a language. Why use it? Because it is easy. Is it fast?"
    qs = related_questions([text], limit=5)
    assert any(q.startswith("What is Python") for q in qs)
    assert any(q.startswith("Why use it") for q in qs)
    assert len(qs) <= 5


def test_dedupe_is_case_insensitive():
    assert dedupe(["Python", "python", "PYTHON", "Django"]) == ["Python", "Django"]
