from app.models.schemas import OperatorInfo


OPERATORS = [
    OperatorInfo(
        code="standardize.trim",
        name="去除首尾空白",
        category="standardize",
        description="本域内对字段值执行首尾空白清理。",
        output_boundary="local_only",
    ),
    OperatorInfo(
        code="key.primary.derive",
        name="主键派生",
        category="key",
        description="基于本域配置字段派生内部主键，仅用于本域内统计和关联。",
        output_boundary="local_only",
    ),
    OperatorInfo(
        code="key.sub.derive",
        name="子键派生",
        category="key",
        description="基于本域配置字段派生内部子键，仅用于本域内细分记录识别。",
        output_boundary="local_only",
    ),
    OperatorInfo(
        code="deid.digest.local",
        name="本域去标识摘要",
        category="deid",
        description="对敏感字段生成本域内摘要，摘要不保存、不出域。",
        output_boundary="local_only",
    ),
    OperatorInfo(
        code="aggregate.threshold",
        name="聚合阈值过滤",
        category="aggregate",
        description="只输出满足最小阈值的单维粗粒度聚合统计。",
        output_boundary="safe_summary",
    ),
    OperatorInfo(
        code="receipt.execution",
        name="执行回执生成",
        category="receipt",
        description="生成不含对象级数据的任务执行状态回执。",
        output_boundary="safe_summary",
    ),
]


def list_operators() -> list[OperatorInfo]:
    return OPERATORS
