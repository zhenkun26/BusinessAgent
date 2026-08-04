"""密码哈希与校验(bcrypt,生产加固)

说明:
- 直接使用 bcrypt 库而非 passlib(passlib 1.7.4 与 bcrypt>=4.1 不兼容,
  会报 __about__ 缺失/72 字节上限异常)。
- 登录校验由 AUTH_REQUIRE_PASSWORD 开关控制(演示环境保持"密码任意"兼容)。
"""

from __future__ import annotations

import bcrypt


def hash_password(plain_password: str) -> str:
    """生成 bcrypt 密码哈希

    Args:
        plain_password: 明文密码(最长 72 字节,bcrypt 硬限制)

    Returns:
        bcrypt 哈希字符串(含 salt)
    """
    if len(plain_password.encode("utf-8")) > 72:
        raise ValueError("密码长度不能超过 72 字节(bcrypt 硬限制)")
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配(恒定时间比较由 bcrypt 内部保证)

    Args:
        plain_password: 用户提交的明文密码
        password_hash: 数据库中的 bcrypt 哈希

    Returns:
        匹配返回 True;哈希格式非法或密码为空返回 False(不抛异常)
    """
    if not plain_password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        # 哈希格式非法(如 NULL/截断的旧数据),按不匹配处理,不泄露差异
        return False
