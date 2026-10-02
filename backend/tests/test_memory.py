from app.memory.store import EpisodicMemory, MemoryItem


def build_memory() -> EpisodicMemory:
    memory = EpisodicMemory()
    memory.add(MemoryItem(id="m1", round=1, kind="speech", text="Ada accused Boris of deflecting suspicion"))
    memory.add(MemoryItem(id="m2", round=1, kind="kill", text="Cleo was found dead at dawn, she was a villager"))
    memory.add(MemoryItem(id="m3", round=2, kind="vote", text="Boris voted to eliminate Ada"))
    memory.add(MemoryItem(id="m4", round=2, kind="speech", text="Dorian told a joke and changed the subject"))
    return memory


def test_retrieve_returns_most_relevant_first():
    memory = build_memory()
    results = memory.retrieve("who voted to eliminate Ada")
    assert results
    assert results[0].item.id == "m3"


def test_retrieve_respects_top_k():
    memory = build_memory()
    assert len(memory.retrieve("village votes suspicion werewolf", k=2)) <= 2


def test_retrieve_empty_memory_is_safe():
    assert EpisodicMemory().retrieve("anything") == []


def test_irrelevant_query_scores_zero():
    memory = EpisodicMemory()
    memory.add(MemoryItem(id="m1", round=1, kind="speech", text="the weather is nice"))
    assert memory.retrieve("quantum chromodynamics") == []
