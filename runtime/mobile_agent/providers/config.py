"""Configuration gate for planner model providers."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

from mobile_agent.agent.planner import Planner, RuleBasedPlanner
from mobile_agent.domain.errors import ErrorCategory, MobileAgentError
from mobile_agent.providers.openai_compatible import (
    ModelTransport,
    OpenAICompatiblePlanner,
    OpenAICompatiblePlannerConfig,
)


@dataclass(frozen=True, slots=True)
class ModelProviderSettings:
    """Explicit settings required before a model planner can be enabled."""

    enabled: bool = False
    provider: str = "rule_based"
    base_url: str = ""
    model: str = ""
    api_key_ref: str = ""
    timeout_seconds: float = 30.0


class SecretResolver(Protocol):
    """Resolve a secret reference into a secret value."""

    def resolve(self, reference: str) -> str:
        """Return the secret value for a configured reference."""


class EnvironmentSecretResolver:
    """Resolve explicitly scoped model secret references from environment variables."""

    _REFERENCE_PREFIX = "env:"
    _ALLOWED_NAME = re.compile(r"MOBILE_AGENT_MODEL_SECRET_[A-Z0-9_]+")

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ

    def resolve(self, reference: str) -> str:
        """Resolve references shaped like env:MOBILE_AGENT_MODEL_SECRET_NAME."""

        if not reference.startswith(self._REFERENCE_PREFIX):
            raise _secret_unavailable("仅支持 env: 形式的模型密钥引用", reference)
        name = reference[len(self._REFERENCE_PREFIX) :]
        if not self._ALLOWED_NAME.fullmatch(name):
            raise _secret_unavailable("模型密钥环境变量名称不在允许范围内", reference)
        value = self._environ.get(name, "")
        if not value:
            raise _secret_unavailable("模型密钥引用未解析到值", reference)
        return value


def model_provider_status(settings: ModelProviderSettings | None = None) -> dict[str, object]:
    """Return redacted model provider status suitable for local UI display."""

    safe_settings = settings or ModelProviderSettings()
    enabled = bool(safe_settings.enabled)
    return {
        "enabled": enabled,
        "provider": safe_settings.provider if enabled else "rule_based",
        "model": safe_settings.model if enabled else "",
        "base_url_configured": bool(safe_settings.base_url),
        "api_key_ref_configured": bool(safe_settings.api_key_ref),
        "timeout_seconds": safe_settings.timeout_seconds,
        "status": "configured" if enabled else "disabled",
    }


_SECRET_REF_FULL = re.compile(r"env:MOBILE_AGENT_MODEL_SECRET_[A-Z0-9_]+")

_ENV_OVERRIDE_NAMES = (
    "MOBILE_AGENT_MODEL_ENABLED",
    "MOBILE_AGENT_MODEL_PROVIDER",
    "MOBILE_AGENT_MODEL_BASE_URL",
    "MOBILE_AGENT_MODEL_NAME",
    "MOBILE_AGENT_MODEL_API_KEY_REF",
    "MOBILE_AGENT_MODEL_TIMEOUT_SECONDS",
)


def read_model_provider_file(config_path: Path) -> ModelProviderSettings:
    """Read the on-disk model provider file without applying env overrides."""

    if not config_path.exists():
        return ModelProviderSettings()
    return _coerce_settings(_read_settings_file(config_path))


def model_provider_config_view(
    settings: ModelProviderSettings,
    config_path: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Return the non-secret on-disk model provider config for the settings UI."""

    env = environ if environ is not None else os.environ
    return {
        "enabled": settings.enabled,
        "provider": settings.provider,
        "base_url": settings.base_url,
        "model": settings.model,
        "api_key_ref": settings.api_key_ref,
        "timeout_seconds": settings.timeout_seconds,
        "config_file": str(config_path),
        "env_override": any(
            env.get(name, "").strip() for name in _ENV_OVERRIDE_NAMES
        ),
    }


def coerce_model_provider_payload(payload: Mapping[str, object]) -> ModelProviderSettings:
    """Coerce a client payload into settings, rejecting unknown fields."""

    allowed = {
        "enabled",
        "provider",
        "base_url",
        "model",
        "api_key_ref",
        "timeout_seconds",
    }
    unknown = sorted(set(str(key) for key in payload) - allowed)
    if unknown:
        raise _invalid_config(f"模型配置包含未知字段：{unknown[0]}")
    if "enabled" not in payload:
        raise _invalid_config("模型配置缺少 enabled 字段")
    return _coerce_settings(payload)


def save_model_provider_settings(
    config_path: Path, settings: ModelProviderSettings
) -> None:
    """Atomically persist non-secret model provider settings with strict permissions.

    密钥值永不经过此函数：api_key_ref 强制 env:MOBILE_AGENT_MODEL_SECRET_* 引用
    模式（ITER-0054 设计决策 1）；临时文件 + os.replace 保证写坏不破坏旧配置。
    """

    if settings.api_key_ref and not _SECRET_REF_FULL.fullmatch(settings.api_key_ref):
        raise _invalid_settings(
            "模型 api_key_ref 只允许 env:MOBILE_AGENT_MODEL_SECRET_* 引用", settings
        )
    if settings.enabled:
        _validate_openai_compatible_settings(settings)
    payload = {
        "enabled": settings.enabled,
        "provider": settings.provider,
        "base_url": settings.base_url,
        "model": settings.model,
        "api_key_ref": settings.api_key_ref,
        "timeout_seconds": settings.timeout_seconds,
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_path.with_suffix(config_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.chmod(0o600)
    os.replace(temporary, config_path)


def load_model_provider_settings(
    default_config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> ModelProviderSettings:
    """Load model provider settings from explicit env, local file, and safe defaults."""

    env = environ if environ is not None else os.environ
    configured_path = env.get("MOBILE_AGENT_MODEL_CONFIG", "").strip()
    config_path = Path(configured_path) if configured_path else default_config_path
    raw_settings: dict[str, object] = {}
    if config_path is not None:
        if config_path.exists():
            raw_settings = _read_settings_file(config_path)
        elif configured_path:
            raise _invalid_config("模型配置文件不存在")
    raw_settings.update(_settings_from_environment(env))
    settings = _coerce_settings(raw_settings)
    if settings.enabled:
        _validate_openai_compatible_settings(settings)
    return settings


def build_planner_from_settings(
    settings: ModelProviderSettings | None = None,
    secret_resolver: SecretResolver | None = None,
    transport: ModelTransport | None = None,
) -> Planner:
    """Build a Planner from explicit settings without changing Runtime defaults."""

    safe_settings = settings or ModelProviderSettings()
    if not safe_settings.enabled:
        return RuleBasedPlanner()
    _validate_openai_compatible_settings(safe_settings)
    if secret_resolver is None:
        raise _model_unavailable("缺少模型密钥解析器", safe_settings)
    try:
        api_key = secret_resolver.resolve(safe_settings.api_key_ref)
    except MobileAgentError:
        raise
    except Exception as error:
        raise _model_unavailable("无法解析模型密钥引用", safe_settings) from error
    if not api_key:
        raise _model_unavailable("模型密钥为空", safe_settings)
    return OpenAICompatiblePlanner(
        OpenAICompatiblePlannerConfig(
            base_url=safe_settings.base_url,
            model=safe_settings.model,
            api_key=api_key,
            timeout_seconds=safe_settings.timeout_seconds,
        ),
        transport,
    )


def _validate_openai_compatible_settings(settings: ModelProviderSettings) -> None:
    if settings.provider != "openai_compatible":
        raise _invalid_settings("仅支持显式 provider=openai_compatible", settings)
    if not settings.base_url.startswith(("http://", "https://")):
        raise _invalid_settings("模型 base_url 必须是 http(s) URL", settings)
    if not settings.model.strip():
        raise _invalid_settings("模型名称不能为空", settings)
    if not settings.api_key_ref.strip():
        raise _invalid_settings("模型 api_key_ref 不能为空", settings)
    if settings.timeout_seconds < 1 or settings.timeout_seconds > 120:
        raise _invalid_settings("模型 timeout_seconds 必须在 1 到 120 秒之间", settings)


def _read_settings_file(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise _invalid_config("无法读取模型配置文件") from error
    if not isinstance(payload, dict):
        raise _invalid_config("模型配置文件必须是 JSON object")
    return {str(key): value for key, value in payload.items()}


def _settings_from_environment(env: Mapping[str, str]) -> dict[str, object]:
    mapping = {
        "enabled": "MOBILE_AGENT_MODEL_ENABLED",
        "provider": "MOBILE_AGENT_MODEL_PROVIDER",
        "base_url": "MOBILE_AGENT_MODEL_BASE_URL",
        "model": "MOBILE_AGENT_MODEL_NAME",
        "api_key_ref": "MOBILE_AGENT_MODEL_API_KEY_REF",
        "timeout_seconds": "MOBILE_AGENT_MODEL_TIMEOUT_SECONDS",
    }
    result: dict[str, object] = {}
    for field, variable in mapping.items():
        raw_value = env.get(variable)
        if raw_value is not None and raw_value.strip():
            result[field] = raw_value.strip()
    return result


def _coerce_settings(raw: Mapping[str, object]) -> ModelProviderSettings:
    return ModelProviderSettings(
        enabled=_coerce_bool(raw.get("enabled", False)),
        provider=_coerce_string(raw.get("provider", "rule_based"), "provider"),
        base_url=_coerce_string(raw.get("base_url", ""), "base_url"),
        model=_coerce_string(raw.get("model", ""), "model"),
        api_key_ref=_coerce_string(raw.get("api_key_ref", ""), "api_key_ref"),
        timeout_seconds=_coerce_timeout(raw.get("timeout_seconds", 30.0)),
    )


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise _invalid_config("模型 enabled 必须是布尔值")


def _coerce_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise _invalid_config(f"模型 {name} 必须是字符串")
    return value.strip()


def _coerce_timeout(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise _invalid_config("模型 timeout_seconds 必须是数字")
    try:
        return float(value)
    except ValueError as error:
        raise _invalid_config("模型 timeout_seconds 必须是数字") from error


def _invalid_config(message: str) -> MobileAgentError:
    return MobileAgentError(
        code="INVALID_ARGUMENT",
        category=ErrorCategory.VALIDATION,
        message=message,
        details={"config": "model_provider"},
    )


def _invalid_settings(message: str, settings: ModelProviderSettings) -> MobileAgentError:
    return MobileAgentError(
        code="INVALID_ARGUMENT",
        category=ErrorCategory.VALIDATION,
        message=message,
        details={
            "provider": settings.provider,
            "enabled": settings.enabled,
            "has_base_url": bool(settings.base_url),
            "has_model": bool(settings.model),
            "has_api_key_ref": bool(settings.api_key_ref),
        },
    )


def _model_unavailable(message: str, settings: ModelProviderSettings) -> MobileAgentError:
    return MobileAgentError(
        code="MODEL_UNAVAILABLE",
        category=ErrorCategory.EXECUTION,
        message=message,
        details={
            "provider": settings.provider,
            "has_api_key_ref": bool(settings.api_key_ref),
        },
    )


def _secret_unavailable(message: str, reference: str) -> MobileAgentError:
    return MobileAgentError(
        code="MODEL_UNAVAILABLE",
        category=ErrorCategory.EXECUTION,
        message=message,
        details={
            "reference_scheme": reference.split(":", 1)[0] if ":" in reference else "",
            "has_reference": bool(reference),
        },
    )
