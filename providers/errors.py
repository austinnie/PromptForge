# providers/errors.py
class ProviderError(Exception):
    """Provider 层通用异常基类"""

class ProviderUnavailable(ProviderError):
    """临时不可用（网络/限流/服务端 5xx），fallback 可以继续尝试下一个"""

class ProviderAuthError(ProviderError):
    """认证失败（401/403），fallback 无意义，应立即中止"""

class ProviderConfigError(ProviderError):
    """配置缺失（缺 API key、缺模型路径），fallback 无意义"""

class AllProvidersFailed(ProviderError):
    """所有 provider 都失败"""