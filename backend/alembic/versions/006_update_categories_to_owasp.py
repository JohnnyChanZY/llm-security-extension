"""update categories to OWASP Top 10 for LLM Applications 2025

Revision ID: 006_owasp_categories
Revises: 005_fix_severity
Create Date: 2026-03-28

更新分类为 OWASP Top 10 for LLM Applications 2025 标准：
- 清空现有分类
- 插入新的 OWASP Top 10 分类
- 将现有事件的 category_id 设为 NULL
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_owasp_categories'
down_revision: Union[str, None] = '005_fix_severity'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """更新分类为 OWASP Top 10 标准"""

    # 1. 将现有事件的 category_id 设为 NULL（旧分类不再有效）
    op.execute("""
        UPDATE historical_events SET category_id = NULL WHERE category_id IS NOT NULL
    """)
    op.execute("""
        UPDATE rss_events SET category_id = NULL WHERE category_id IS NOT NULL
    """)

    # 2. 清空现有分类
    op.execute("DELETE FROM categories")

    # 3. 插入新的 OWASP Top 10 分类
    op.execute("""
        INSERT INTO categories (code, name, description, is_active) VALUES
        ('LLM01', '提示注入', '通过精心设计的输入操纵LLM行为，包括直接和间接提示注入', TRUE),
        ('LLM02', '不安全的输出处理', '未能验证、净化或处理LLM输出，可能导致XSS、CSRF等安全风险', TRUE),
        ('LLM03', '训练数据投毒', '篡改训练数据或微调数据，引入后门、偏见或漏洞', TRUE),
        ('LLM04', '模型拒绝服务', '通过特定输入消耗过量资源，导致服务降级或中断', TRUE),
        ('LLM05', '供应链漏洞', '预训练模型、数据集、插件或依赖项中的漏洞', TRUE),
        ('LLM06', '敏感信息泄露', 'LLM无意中泄露训练数据中的敏感信息、个人数据或机密', TRUE),
        ('LLM07', '不安全的插件设计', 'LLM插件或扩展中的安全漏洞，如输入验证不足、权限过大', TRUE),
        ('LLM08', '过度代理', '赋予LLM过多权限、能力或自主决策能力，导致意外操作', TRUE),
        ('LLM09', '过度依赖', '盲目信任LLM输出，缺乏人工审核，导致错误决策', TRUE),
        ('LLM10', '模型窃取', '未授权访问、复制或提取专有模型权重或参数', TRUE),
        ('other', '其他', '其他类型的LLM安全问题', TRUE)
    """)


def downgrade() -> None:
    """回滚：恢复原有分类"""

    # 1. 将现有事件的 category_id 设为 NULL
    op.execute("""
        UPDATE historical_events SET category_id = NULL WHERE category_id IS NOT NULL
    """)
    op.execute("""
        UPDATE rss_events SET category_id = NULL WHERE category_id IS NOT NULL
    """)

    # 2. 清空 OWASP 分类
    op.execute("DELETE FROM categories")

    # 3. 恢复原有分类
    op.execute("""
        INSERT INTO categories (code, name, description, is_active) VALUES
        ('prompt_injection', '提示注入', '通过精心设计的输入提示来操纵LLM的行为', TRUE),
        ('data_leakage', '数据泄露', '模型意外泄露训练数据或敏感信息', TRUE),
        ('jailbreak', '越狱攻击', '绕过模型的安全限制和约束', TRUE),
        ('adversarial_attack', '对抗攻击', '通过对抗样本欺骗模型', TRUE),
        ('model_theft', '模型窃取', '通过查询复制模型参数或行为', TRUE),
        ('privacy_violation', '隐私侵犯', '侵犯用户隐私或泄露个人信息', TRUE),
        ('misinformation', '虚假信息', '模型生成虚假或误导性信息', TRUE),
        ('other', '其他', '其他类型的安全问题', TRUE)
    """)
