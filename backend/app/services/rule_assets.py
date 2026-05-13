from uuid import uuid4

from app.models.schemas import RuleSnippet, RuleSnippetCreate, RuleTemplate, RuleTemplateCreate
from app.services.audit import utc_now
from app.services.rule_logic import count_rule_items


def create_rule_template(payload: RuleTemplateCreate) -> RuleTemplate:
    now = utc_now()
    return RuleTemplate(
        id=str(uuid4()),
        name=payload.name,
        description=payload.description,
        rules=payload.rules,
        rules_count=count_rule_items(payload.rules),
        created_by=payload.created_by,
        created_at=now,
        updated_at=now,
    )


def create_rule_snippet(payload: RuleSnippetCreate) -> RuleSnippet:
    now = utc_now()
    return RuleSnippet(
        id=str(uuid4()),
        name=payload.name,
        description=payload.description,
        rule=payload.rule,
        created_by=payload.created_by,
        created_at=now,
        updated_at=now,
    )
