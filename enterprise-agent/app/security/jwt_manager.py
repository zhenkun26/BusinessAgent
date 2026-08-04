"""JWT 生命周期管理(P0-5)"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from loguru import logger

from app.config import get_settings


class JWTManager:
    """JWT 生命周期管理器(对应 v3 方案 18.5 / 10.3 节)

    功能:
    - 解析过期时间
    - 检查是否过期(含时钟偏移)
    - 检查是否即将过期
    - 自动刷新(若有刷新回调)
    """

    def __init__(
        self,
        refresh_callback: Optional[callable] = None,
        clock_skew_seconds: int = 30,
    ):
        self.refresh_callback = refresh_callback
        self.clock_skew = clock_skew_seconds
        self._settings = get_settings()

    def get_expiry(self, token: str) -> datetime:
        """解析 JWT 过期时间"""
        try:
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False},
            )
            return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        except Exception as e:
            logger.warning(f"JWT 解析失败: {e}")
            return datetime.min.replace(tzinfo=timezone.utc)

    def is_expired(self, token: str) -> bool:
        """检查是否过期(含时钟偏移)"""
        expiry = self.get_expiry(token)
        now = datetime.now(timezone.utc)
        return now + timedelta(seconds=self.clock_skew) >= expiry

    def will_expire_within(self, token: str, seconds: int) -> bool:
        """检查是否在指定时间内过期"""
        expiry = self.get_expiry(token)
        now = datetime.now(timezone.utc)
        return now + timedelta(seconds=seconds) >= expiry

    async def refresh_if_needed(self, token: str, min_seconds: int = 300) -> str:
        """若即将过期则刷新"""
        if self.will_expire_within(token, min_seconds):
            if self.refresh_callback is None:
                raise RuntimeError("无刷新回调,无法刷新 JWT")
            new_token = await self.refresh_callback(token)
            logger.info("JWT 已刷新")
            return new_token
        return token

    def decode(self, token: str) -> dict:
        """解码 JWT(验证签名)"""
        return jwt.decode(
            token,
            self._settings.jwt_secret_key,
            algorithms=[self._settings.jwt_algorithm],
        )

    def encode(self, payload: dict) -> str:
        """生成 JWT"""
        return jwt.encode(
            payload,
            self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )


# 全局单例
_jwt_manager: Optional[JWTManager] = None


def get_jwt_manager() -> JWTManager:
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager
