from app.investigations import InvestigationStore


def test_create_and_list_investigation(tmp_path):
    store = InvestigationStore(str(tmp_path / "investigations.db"))

    investigation = store.create("Signal investigation", "Initial field notes")

    assert investigation["id"] >= 1
    assert investigation["title"] == "Signal investigation"
    assert investigation["notes"] == "Initial field notes"
    assert investigation["status"] == "open"
    assert investigation["observation_ids"] == []

    listed = store.list()
    assert len(listed) == 1
    assert listed[0]["id"] == investigation["id"]


def test_attach_observation_is_idempotent(tmp_path):
    store = InvestigationStore(str(tmp_path / "investigations.db"))
    investigation = store.create("Test")

    assert store.attach_observation(investigation["id"], 42) is True
    assert store.attach_observation(investigation["id"], 42) is True

    saved = store.get(investigation["id"])
    assert saved["observation_ids"] == [42]


def test_attach_to_missing_investigation_returns_false(tmp_path):
    store = InvestigationStore(str(tmp_path / "investigations.db"))

    assert store.attach_observation(9999, 1) is False


def test_investigations_persist_across_store_instances(tmp_path):
    path = str(tmp_path / "investigations.db")
    first = InvestigationStore(path)
    created = first.create("Persistent case")
    first.attach_observation(created["id"], 7)

    second = InvestigationStore(path)
    loaded = second.get(created["id"])

    assert loaded["title"] == "Persistent case"
    assert loaded["observation_ids"] == [7]


def test_empty_title_gets_default(tmp_path):
    store = InvestigationStore(str(tmp_path / "investigations.db"))

    investigation = store.create("", "notes")

    assert investigation["title"] == "RF investigation"
