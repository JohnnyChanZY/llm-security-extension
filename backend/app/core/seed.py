"""
数据库种子数据
初始化管理员账号、预设模型、分类和系统配置
"""
import json
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.config import settings
from app.models.user import User
from app.models.model import Model
from app.models.category import Category
from app.models.system_config import SystemConfig


def seed_all():
    """执行所有种子数据"""
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_categories(db)
        seed_models(db)
        seed_system_configs(db)
        db.commit()
        print("种子数据初始化完成")
    except Exception as e:
        print(f"种子数据初始化失败: {e}")
        db.rollback()
    finally:
        db.close()


def seed_admin(db: Session):
    """初始化管理员账号"""
    admin = db.query(User).filter(User.email == settings.admin_email).first()
    if not admin:
        admin = User(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            nickname="管理员",
            is_admin=True,
            is_active=True
        )
        db.add(admin)
        print(f"创建管理员账号: {settings.admin_email}")


def seed_categories(db: Session):
    """初始化安全事件分类 - 基于 OWASP Top 10 for LLM Applications 2025"""
    categories = [
        {"code": "LLM01", "name": "提示注入", "description": "通过精心设计的输入操纵LLM行为，包括直接和间接提示注入"},
        {"code": "LLM02", "name": "不安全的输出处理", "description": "未能验证、净化或处理LLM输出，可能导致XSS、CSRF等安全风险"},
        {"code": "LLM03", "name": "训练数据投毒", "description": "篡改训练数据或微调数据，引入后门、偏见或漏洞"},
        {"code": "LLM04", "name": "模型拒绝服务", "description": "通过特定输入消耗过量资源，导致服务降级或中断"},
        {"code": "LLM05", "name": "供应链漏洞", "description": "预训练模型、数据集、插件或依赖项中的漏洞"},
        {"code": "LLM06", "name": "敏感信息泄露", "description": "LLM无意中泄露训练数据中的敏感信息、个人数据或机密"},
        {"code": "LLM07", "name": "不安全的插件设计", "description": "LLM插件或扩展中的安全漏洞，如输入验证不足、权限过大"},
        {"code": "LLM08", "name": "过度代理", "description": "赋予LLM过多权限、能力或自主决策能力，导致意外操作"},
        {"code": "LLM09", "name": "过度依赖", "description": "盲目信任LLM输出，缺乏人工审核，导致错误决策"},
        {"code": "LLM10", "name": "模型窃取", "description": "未授权访问、复制或提取专有模型权重或参数"},
        {"code": "other", "name": "其他", "description": "其他类型的LLM安全问题"},
    ]

    for cat_data in categories:
        existing = db.query(Category).filter(Category.code == cat_data["code"]).first()
        if not existing:
            category = Category(**cat_data, is_active=True)
            db.add(category)
            print(f"创建分类: {cat_data['name']}")


def seed_models(db: Session):
    """初始化预设模型列表"""
    models = [
        # 国际闭源模型
        {"name": "GPT-4", "vendor": "OpenAI", "description": "最新旗舰模型", "sort_order": 1},
        {"name": "GPT-3.5", "vendor": "OpenAI", "description": "通用对话模型", "sort_order": 2},
        {"name": "Claude", "vendor": "Anthropic", "description": "安全导向模型", "sort_order": 3},
        {"name": "Gemini", "vendor": "Google", "description": "多模态模型", "sort_order": 4},
        {"name": "Copilot", "vendor": "Microsoft", "description": "代码辅助模型", "sort_order": 5},
        # 国产模型
        {"name": "通义千问", "vendor": "阿里云", "description": "Qwen系列", "sort_order": 10},
        {"name": "文心一言", "vendor": "百度", "description": "ERNIE系列", "sort_order": 11},
        {"name": "GLM", "vendor": "智谱AI", "description": "ChatGLM系列", "sort_order": 12},
        {"name": "Kimi", "vendor": "月之暗面", "description": "长上下文模型", "sort_order": 13},
        {"name": "DeepSeek", "vendor": "深度求索", "description": "开源推理模型", "sort_order": 14},
        {"name": "讯飞星火", "vendor": "科大讯飞", "description": "认知大模型", "sort_order": 15},
        {"name": "百川", "vendor": "百川智能", "description": "开源大模型", "sort_order": 16},
        {"name": "混元", "vendor": "腾讯", "description": "多模态模型", "sort_order": 17},
        # 开源模型
        {"name": "LLaMA", "vendor": "Meta", "description": "开源基座模型", "sort_order": 20},
        {"name": "Mistral", "vendor": "Mistral AI", "description": "高效开源模型", "sort_order": 21},
        {"name": "Qwen", "vendor": "阿里云", "description": "开源多语言模型", "sort_order": 22},
        {"name": "Yi", "vendor": "零一万物", "description": "双语开源模型", "sort_order": 23},
        {"name": "Phi", "vendor": "Microsoft", "description": "小参数高性能模型", "sort_order": 24},
        {"name": "Falcon", "vendor": "TII", "description": "开源大模型", "sort_order": 25},
    ]

    for model_data in models:
        existing = db.query(Model).filter(Model.name == model_data["name"]).first()
        if not existing:
            model = Model(**model_data, is_active=True)
            db.add(model)
            print(f"创建模型: {model_data['name']}")


def seed_system_configs(db: Session):
    """初始化系统配置"""
    # 默认关键词列表
    default_keywords = [
        "vulnerability", "exploit", "CVE", "RCE", "zero-day",
        "injection", "jailbreak", "bypass", "attack", "malicious",
        "compromise", "breach", "threat",
        "prompt injection", "adversarial attack", "data poisoning",
        "model extraction", "model stealing", "membership inference",
        "backdoor", "alignment", "reward hacking",
        "security advisory", "security bulletin", "security fix",
        "security patch", "vulnerability disclosure",
        "data leakage", "data exfiltration", "privacy attack",
        "training data leak",
        "漏洞", "注入", "越狱", "绕过", "攻击", "数据泄露"
    ]

    configs = [
        {"config_key": "llm_rating_enabled", "config_value": "false", "description": "LLM自动评级开关（与分类开关独立）"},
        {"config_key": "llm_classify_enabled", "config_value": "false", "description": "LLM自动分类开关（与评级开关独立）"},
        {"config_key": "llm_batch_size", "config_value": "30", "description": "LLM单批次处理事件数量"},
        {"config_key": "llm_request_interval", "config_value": "2", "description": "LLM请求间隔时间（秒）"},
        {"config_key": "keyword_filter_enabled", "config_value": "true", "description": "关键词筛选开关"},
        {"config_key": "filter_keywords", "config_value": json.dumps(default_keywords, ensure_ascii=False), "description": "筛选关键词列表(JSON数组)"},
    ]

    for config_data in configs:
        existing = db.query(SystemConfig).filter(
            SystemConfig.config_key == config_data["config_key"]
        ).first()
        if not existing:
            config = SystemConfig(**config_data)
            db.add(config)
            print(f"创建配置: {config_data['config_key']}")


if __name__ == "__main__":
    seed_all()
