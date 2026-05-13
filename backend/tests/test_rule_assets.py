import unittest

from app.models.schemas import RuleSnippetCreate, RuleTemplateCreate
from app.services.rule_assets import create_rule_snippet, create_rule_template


class RuleAssetTests(unittest.TestCase):
    def test_create_rule_template_counts_nested_rules(self) -> None:
        template = create_rule_template(
            RuleTemplateCreate(
                name="跨部门资格复核模板",
                description="复用组合规则结构",
                created_by="经办员A",
                rules=[
                    {
                        "type": "group",
                        "logic": "and",
                        "children": [
                            {"type": "rule", "field": "department", "operator": "eq", "value": "民政"},
                            {"type": "rule", "field": "benefit_status", "operator": "eq", "value": "正常"},
                        ],
                    }
                ],
            )
        )

        self.assertEqual(template.rules_count, 2)
        self.assertEqual(template.created_by, "经办员A")

    def test_create_rule_snippet_keeps_rule_payload(self) -> None:
        snippet = create_rule_snippet(
            RuleSnippetCreate(
                name="正常状态",
                description="单条状态判断",
                created_by="经办员A",
                rule={"type": "rule", "field": "benefit_status", "operator": "eq", "value": "正常"},
            )
        )

        self.assertEqual(snippet.rule["field"], "benefit_status")
        self.assertEqual(snippet.rule["operator"], "eq")


if __name__ == "__main__":
    unittest.main()
