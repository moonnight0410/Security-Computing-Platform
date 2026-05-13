import unittest

from app.services.rule_logic import count_rule_items, evaluate_rule_tree, flatten_rule_descriptors


class RuleLogicTests(unittest.TestCase):
    def nested_rules(self) -> list[dict[str, object]]:
        return [
            {
                "type": "group",
                "logic": "and",
                "children": [
                    {"type": "rule", "field": "department", "operator": "eq", "value": "民政"},
                    {
                        "type": "group",
                        "logic": "or",
                        "children": [
                            {"type": "rule", "field": "benefit_status", "operator": "eq", "value": "正常"},
                            {"type": "rule", "field": "amount", "operator": "gte", "value": 1000},
                        ],
                    },
                ],
            }
        ]

    def test_count_rule_items_handles_nested_groups(self) -> None:
        self.assertEqual(count_rule_items(self.nested_rules()), 3)

    def test_evaluate_rule_tree_handles_and_or_nesting(self) -> None:
        row = {"department": "民政", "benefit_status": "正常", "amount": "800"}
        self.assertTrue(evaluate_rule_tree(row, self.nested_rules()))

    def test_evaluate_rule_tree_returns_false_when_group_fails(self) -> None:
        row = {"department": "医保", "benefit_status": "异常", "amount": "800"}
        self.assertFalse(evaluate_rule_tree(row, self.nested_rules()))

    def test_evaluate_rule_tree_returns_unknown_when_or_branch_is_incomplete(self) -> None:
        row = {"department": "民政", "benefit_status": "", "amount": ""}
        self.assertIsNone(evaluate_rule_tree(row, self.nested_rules()))

    def test_flatten_rule_descriptors_keeps_group_and_rule_paths(self) -> None:
        descriptors = flatten_rule_descriptors(self.nested_rules())
        self.assertTrue(any(item["node_type"] == "group" and item["path"] == "root" for item in descriptors))
        self.assertTrue(any(item["node_type"] == "rule" and item["path"] == "root.0" for item in descriptors))
        self.assertTrue(any(item["node_type"] == "rule" and item["path"] == "root.1.1" for item in descriptors))


if __name__ == "__main__":
    unittest.main()
