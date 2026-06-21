from trailo_protocols.selection import filter_race_by_context


def test_filter_race_by_context_keeps_all_without_group_selection():
    race = {
        "groups": [{"id": "g1"}, {"id": "g2"}],
        "persons": [{"id": "p1", "group_id": "g1"}, {"id": "p2", "group_id": "g2"}],
        "results": [{"id": "r1", "person_id": "p1"}, {"id": "r2", "person_id": "p2"}],
        "organizations": [{"id": "o1"}, {"id": "o2"}],
        "courses": [{"id": "c1"}, {"id": "c2"}],
    }
    out = filter_race_by_context(race, {"selection": {"object": "Person", "ids": ["p1"]}})
    assert out is race


def test_filter_race_by_context_filters_groups_persons_results():
    race = {
        "groups": [{"id": "g1", "course_id": "c1"}, {"id": "g2", "course_id": "c2"}],
        "persons": [
            {"id": "p1", "group_id": "g1", "organization_id": "o1"},
            {"id": "p2", "group_id": "g2", "organization_id": "o2"},
        ],
        "results": [{"id": "r1", "person_id": "p1"}, {"id": "r2", "person_id": "p2"}],
        "organizations": [{"id": "o1"}, {"id": "o2"}],
        "courses": [{"id": "c1"}, {"id": "c2"}],
    }
    ctx = {"selection": {"object": "Group", "ids": ["g2"]}}
    out = filter_race_by_context(race, ctx)
    assert [g["id"] for g in out["groups"]] == ["g2"]
    assert [p["id"] for p in out["persons"]] == ["p2"]
    assert [r["id"] for r in out["results"]] == ["r2"]
    assert [o["id"] for o in out["organizations"]] == ["o2"]
    assert [c["id"] for c in out["courses"]] == ["c2"]

