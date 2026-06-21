"""Apply SportOrg plugin entity notifications to a race dict snapshot."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

ENTITY_LIST_KEYS = {
    "Person": "persons",
    "Result": "results",
    "Group": "groups",
    "Course": "courses",
    "Organization": "organizations",
}


def _entity_type(object_name: str) -> str:
    if object_name.startswith("Result"):
        return "Result"
    return object_name


def _entity_id(entity: Dict[str, Any]) -> str:
    return str(entity.get("id", ""))


def _merge_list_item(
    items: List[Dict[str, Any]], entity: Dict[str, Any], operation: str
) -> List[Dict[str, Any]]:
    entity_id = _entity_id(entity)
    if operation == "deleted":
        return [item for item in items if _entity_id(item) != entity_id]

    updated = list(items)
    for index, item in enumerate(updated):
        if _entity_id(item) == entity_id:
            updated[index] = entity
            return updated

    if operation in ("created", "updated", "snapshot"):
        return items + [entity]
    return items


def apply_entity_notification(
    race: Dict[str, Any], method: str, params: Dict[str, Any]
) -> Dict[str, Any]:
    operation = str(params.get("operation", "updated"))
    entity = params.get("entity")
    if not isinstance(entity, dict):
        return race

    object_name = str(entity.get("object", ""))
    entity_type = _entity_type(object_name)

    if method == "sportorg.race.update" or entity_type == "Race":
        if operation == "deleted":
            return race
        return dict(entity)

    list_key = ENTITY_LIST_KEYS.get(entity_type)
    if not list_key:
        return race

    race = dict(race)
    items = list(race.get(list_key) or [])
    race[list_key] = _merge_list_item(items, entity, operation)
    return race
