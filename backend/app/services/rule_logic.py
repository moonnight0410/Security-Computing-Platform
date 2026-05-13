from copy import deepcopy
from typing import Any


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def is_group_node(node: dict[str, Any]) -> bool:
    return str(node.get("type") or "").lower() == "group" or ("logic" in node and "children" in node)


def normalize_rule_node(node: dict[str, Any]) -> dict[str, Any]:
    if is_group_node(node):
        logic = str(node.get("logic") or "and").lower()
        if logic not in {"and", "or"}:
            logic = "and"
        children = [
            normalize_rule_node(child)
            for child in node.get("children", [])
            if isinstance(child, dict)
        ]
        return {
            "type": "group",
            "logic": logic,
            "children": children,
        }

    return {
        "type": "rule",
        "field": normalize_text(node.get("field")),
        "operator": normalize_text(node.get("operator")),
        "value": deepcopy(node.get("value")),
    }


def normalize_rule_tree(rules: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rules) == 1 and isinstance(rules[0], dict) and is_group_node(rules[0]):
        return normalize_rule_node(rules[0])
    return {
        "type": "group",
        "logic": "and",
        "children": [normalize_rule_node(rule) for rule in rules if isinstance(rule, dict)],
    }


def count_rule_items(rules: list[dict[str, Any]]) -> int:
    def count_node(node: dict[str, Any]) -> int:
        if is_group_node(node):
            return sum(count_node(child) for child in node.get("children", []) if isinstance(child, dict))
        return 1 if normalize_text(node.get("field")) and normalize_text(node.get("operator")) else 0

    root = normalize_rule_tree(rules)
    return count_node(root)


def compare_leaf_value(actual: str, operator: str, expected: Any) -> bool | None:
    if operator in {"exists", "not_empty"}:
        return bool(actual)
    if not actual:
        return None
    if operator == "eq":
        return actual == str(expected)
    if operator == "neq":
        return actual != str(expected)
    if operator == "in":
        if not isinstance(expected, list):
            return None
        return actual in {str(item) for item in expected}
    if operator in {"gte", "lte"}:
        try:
            actual_num = float(actual)
            expected_num = float(expected)
        except (TypeError, ValueError):
            return None
        return actual_num >= expected_num if operator == "gte" else actual_num <= expected_num
    return None


def evaluate_rule_tree(row: dict[str, str], rules: list[dict[str, Any]]) -> bool | None:
    def evaluate_node(node: dict[str, Any]) -> bool | None:
        if is_group_node(node):
            results = [evaluate_node(child) for child in node.get("children", []) if isinstance(child, dict)]
            if not results:
                return None
            logic = str(node.get("logic") or "and").lower()
            if logic == "or":
                if any(result is True for result in results):
                    return True
                if all(result is False for result in results):
                    return False
                return None

            if any(result is False for result in results):
                return False
            if all(result is True for result in results):
                return True
            return None

        field = normalize_text(node.get("field"))
        operator = normalize_text(node.get("operator"))
        if not field or not operator:
            return None
        return compare_leaf_value(normalize_text(row.get(field)), operator, node.get("value"))

    return evaluate_node(normalize_rule_tree(rules))


def comparable_rule_value(value: Any) -> Any:
    if isinstance(value, list):
        return [comparable_rule_value(item) for item in value]
    if isinstance(value, dict):
        return {key: comparable_rule_value(item) for key, item in sorted(value.items())}
    return value


def flatten_rule_descriptors(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root = normalize_rule_tree(rules)
    descriptors: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], path: str) -> None:
        if is_group_node(node):
            descriptors.append(
                {
                    "path": path,
                    "node_type": "group",
                    "logic": str(node.get("logic") or "and"),
                }
            )
            for index, child in enumerate(node.get("children", [])):
                if isinstance(child, dict):
                    walk(child, f"{path}.{index}")
            return

        descriptors.append(
            {
                "path": path,
                "node_type": "rule",
                "field": normalize_text(node.get("field")),
                "operator": normalize_text(node.get("operator")),
                "value": comparable_rule_value(node.get("value")),
            }
        )

    walk(root, "root")
    return descriptors
