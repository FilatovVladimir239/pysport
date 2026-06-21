from trailo_protocols.race_sync import apply_entity_notification


def test_apply_result_update_merges_into_race():
    race = {
        "id": "race-1",
        "results": [{"id": "r1", "object": "ResultManual", "trailo_score": 1}],
        "persons": [],
    }
    updated = apply_entity_notification(
        race,
        "sportorg.result.update",
        {
            "operation": "updated",
            "entity": {
                "id": "r1",
                "object": "ResultManual",
                "trailo_score": 5,
            },
        },
    )
    assert updated["results"][0]["trailo_score"] == 5


def test_apply_race_update_replaces_snapshot():
    race = {"id": "race-1", "settings": {"result_processing_mode": "time"}}
    updated = apply_entity_notification(
        race,
        "sportorg.race.update",
        {
            "operation": "updated",
            "entity": {
                "id": "race-1",
                "object": "Race",
                "settings": {"result_processing_mode": "trailo"},
            },
        },
    )
    assert updated["settings"]["result_processing_mode"] == "trailo"
