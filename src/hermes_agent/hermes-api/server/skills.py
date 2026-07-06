"""
skills.py — gestão de toolsets por perfil.
Armazena o estado em ENABLED_TOOLSETS no .env do perfil (não toca no config.yaml global).
"""

from pathlib import Path

from hermes_fs import load_env
from lifecycle import _write_env


def available_toolsets() -> dict:
    """Retorna o dicionário TOOLSETS do hermes-agent (mesmo venv)."""
    from toolsets import TOOLSETS  # noqa: PLC0415
    return TOOLSETS


def enabled_for_profile(d: Path) -> set[str]:
    """Lê ENABLED_TOOLSETS do .env do perfil."""
    env = load_env(d)
    raw = env.get("ENABLED_TOOLSETS", "")
    return {t.strip() for t in raw.split(",") if t.strip()}


def list_skills(d: Path) -> list[dict]:
    """
    Retorna todos os toolsets disponíveis com enabled: true/false para o perfil.
    Toolsets compostos (hermes-*) são omitidos — listamos os atômicos.
    """
    all_ts = available_toolsets()
    enabled = enabled_for_profile(d)
    result = []
    for name, meta in sorted(all_ts.items()):
        # Omite toolsets internos/compostos hermes-prefixed
        if name.startswith("hermes-"):
            continue
        result.append({
            "name": name,
            "description": meta.get("description", ""),
            "tools": meta.get("tools", []),
            "enabled": name in enabled,
        })
    return result


def set_skills(d: Path, enable: list[str], disable: list[str]) -> list[dict]:
    """
    Atualiza ENABLED_TOOLSETS no .env do perfil.
    Valida que os nomes existem, retorna a lista final.
    """
    all_ts = available_toolsets()
    unknown = [t for t in (enable + disable) if t not in all_ts]
    if unknown:
        raise ValueError(f"Toolsets desconhecidos: {unknown}")

    current = enabled_for_profile(d)
    current |= set(enable)
    current -= set(disable)

    env = load_env(d)
    env["ENABLED_TOOLSETS"] = ",".join(sorted(current))
    _write_env(d, env)

    return list_skills(d)
