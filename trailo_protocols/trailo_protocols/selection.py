"""Filter SportOrg race dict based on host UI selection."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Set


def _as_id_set(values: Any) -> Set[str]:
    if not isinstance(values, list):
        return set()
    out: Set[str] = set()
    for item in values:
        if item is None:
            continue
        out.add(str(item))
    return out


def _selection_group_ids(context: Optional[Dict[str, Any]]) -> Set[str]:
    if not isinstance(context, dict):
        return set()
    selection = context.get("selection", {})
    if not isinstance(selection, dict):
        return set()
    if str(selection.get("object") or "") != "Group":
        return set()
    return _as_id_set(selection.get("ids"))


def _filter_by_ids(items: Any, allowed_ids: Set[str]) -> list:
    if not isinstance(items, list):
        return []
    if not allowed_ids:
        return list(items)
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("id")) in allowed_ids:
            out.append(item)
    return out


def filter_race_by_context(race: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a race dict containing only entities related to selected groups.

    If context does not contain group selection, returns the input race unchanged.
    """
    group_ids = _selection_group_ids(context)
    if not group_ids:
        return race

    groups = _filter_by_ids(race.get("groups"), group_ids)
    if not groups:
        # Selection exists but no matching groups found in snapshot: keep unchanged.
        return race

    allowed_group_ids = {str(group.get("id")) for group in groups if isinstance(group, dict)}

    persons = []
    person_ids: Set[str] = set()
    org_ids: Set[str] = set()
    for person in race.get("persons") or []:
        if not isinstance(person, dict):
            continue
        if str(person.get("group_id")) not in allowed_group_ids:
            continue
        persons.append(person)
        if person.get("id") is not None:
            person_ids.add(str(person.get("id")))
        if person.get("organization_id") is not None:
            org_ids.add(str(person.get("organization_id")))

    results = []
    for result in race.get("results") or []:
        if not isinstance(result, dict):
            continue
        pid = result.get("person_id")
        if pid is None:
            continue
        if str(pid) in person_ids:
            results.append(result)

    courses = list(race.get("courses") or [])
    course_ids: Set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        cid = group.get("course_id")
        if cid is not None:
            course_ids.add(str(cid))
        course = group.get("course")
        if isinstance(course, dict) and course.get("id") is not None:
            course_ids.add(str(course.get("id")))
    if course_ids:
        courses = _filter_by_ids(race.get("courses"), course_ids)

    organizations = list(race.get("organizations") or [])
    if org_ids:
        organizations = _filter_by_ids(race.get("organizations"), org_ids)

    filtered = dict(race)
    filtered["groups"] = groups
    filtered["persons"] = persons
    filtered["results"] = results
    filtered["courses"] = courses
    filtered["organizations"] = organizations
    return filtered

