"""
provision.py — provisionamento determinístico de perfis Hermes.
Reimplementa em Python os passos do create-profile (Phases 0-2, 4.4-4.5),
SEM invocar LLM, agente Root ou qualquer canal de conversa.
Toda operação é filesystem + processos.
"""

import os
import re
import shutil
import time
from pathlib import Path

from hermes_fs import HERMES_DIR, HERMES_ROOT, PROJECT_ROOT, SAFE_ID, SKILLS_DIR, load_env

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

# Portas base alocadas dinamicamente a partir de 3100 (3000 = global, 3001+ = perfis)
_BRIDGE_PORT_START = 3100
_GATEWAY_PORT_START = 8810


def _provider_env_key(provider: str) -> str:
    """Map provider name to env var key (e.g. 'anthropic' → 'ANTHROPIC_API_KEY')."""
    mapping = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "ollama": "OLLAMA_API_KEY",
    }
    return mapping.get(provider.lower(), f"{provider.upper()}_API_KEY")


def _generate_profile_config(d: Path, provider: str) -> None:
    """
    Gera um config.yaml per-profile com o provider escolhido.
    Copia a estrutura global (se existir) e sobrescreve o provider.
    """
    import yaml

    global_config = PROJECT_ROOT / "config.base.yaml"
    cfg = {}
    if global_config.exists():
        try:
            cfg = yaml.safe_load(global_config.read_text()) or {}
        except Exception:
            cfg = {}

    if provider:
        cfg["provider"] = provider

    (d / "config.yaml").write_text(yaml.dump(cfg, default_flow_style=False), encoding="utf-8")


def _next_ports() -> tuple[int, int]:
    """Encontra o próximo par (bridge_port, gateway_port) livre."""
    used_bridge: set[int] = set()
    used_gateway: set[int] = set()
    if HERMES_ROOT.exists():
        for d in HERMES_ROOT.iterdir():
            if d.is_dir():
                env = load_env(d)
                try:
                    used_bridge.add(int(env["BRIDGE_PORT"]))
                except (KeyError, ValueError):
                    pass
                try:
                    used_gateway.add(int(env["GATEWAY_PORT"]))
                except (KeyError, ValueError):
                    pass

    bp = _BRIDGE_PORT_START
    while bp in used_bridge:
        bp += 1

    gp = _GATEWAY_PORT_START
    while gp in used_gateway:
        gp += 1

    return bp, gp


def _global_env_keys() -> dict[str, str]:
    """Lê chaves do .env global do Hermes (sem expor valores sensíveis aqui)."""
    global_env_file = HERMES_DIR / ".env"
    if not global_env_file.exists():
        global_env_file = PROJECT_ROOT / ".env"
    env: dict[str, str] = {}
    if global_env_file.exists():
        for line in global_env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _render_soul(name: str, description: str, objective: str,
                 personality: str, language: str, initial_prompt: str) -> str:
    tmpl = TEMPLATES_DIR / "SOUL.sdr.md"
    soul = tmpl.read_text(encoding="utf-8")
    replacements = {
        "{{NAME}}": name,
        "{{DESCRIPTION}}": description,
        "{{OBJECTIVE}}": objective,
        "{{PERSONALITY}}": personality,
        "{{LANGUAGE}}": language,
        "{{INITIAL_PROMPT}}": initial_prompt,
    }
    for k, v in replacements.items():
        soul = soul.replace(k, v)
    return soul


def _render_produto(name: str, description: str) -> str:
    tmpl = TEMPLATES_DIR / "produto.sdr.md"
    produto = tmpl.read_text(encoding="utf-8")
    produto = produto.replace("{{NAME}}", name).replace("{{DESCRIPTION}}", description)
    return produto


WHATSAPP_MODES = ("bot", "self-chat", "mixed")


def create_profile(
    profile_id: str,
    name: str,
    description: str = "",
    objective: str = "",
    personality: str = "",
    language: str = "pt-BR",
    model: str = "",
    temperature: float | None = None,
    initial_prompt: str = "",
    provider: str = "",
    provider_api_key: str = "",
    whatsapp_mode: str = "bot",
    whatsapp_owner_number: str = "",
) -> dict:
    """
    Cria um perfil Hermes de forma determinística (sem LLM/agente Root).
    Retorna o dict do perfil criado.
    Levanta ValueError se o profile_id for inválido ou já existir.
    """
    if not SAFE_ID.match(profile_id):
        raise ValueError(f"profile_id inválido: '{profile_id}'. Use apenas letras, números e hífens.")
    if whatsapp_mode not in WHATSAPP_MODES:
        raise ValueError(f"whatsapp_mode inválido: '{whatsapp_mode}'. Use um de {WHATSAPP_MODES}.")

    d = HERMES_ROOT / profile_id
    if d.exists():
        raise ValueError(f"Perfil '{profile_id}' já existe.")

    bridge_p, gateway_p = _next_ports()
    global_env = _global_env_keys()

    # Modelo padrão se não especificado
    if not model:
        model = global_env.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    # ── Phase 0: estrutura de diretórios ──────────────────────────────────────
    dirs = [
        d, d / "logs", d / "sessions", d / "memories" / "contacts",
        d / "knowledge", d / "backups", d / "cache", d / "audio_cache",
        d / "image_cache", d / "pairing", d / "qr", d / "sandboxes",
        d / "hooks",
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: config.yaml (per-profile, com provider) ─────────────────────
    _generate_profile_config(d, provider)

    # ── Phase 2: .env do perfil ────────────────────────────────────────────────
    env_lines = [
        f"# =====================================================================",
        f"# PERFIL: {profile_id}",
        f"# Criado por: vya-workforce-api",
        f"# Data: {time.strftime('%Y-%m-%d %H:%M')}",
        f"# =====================================================================",
        f"PROFILE_ID={profile_id}",
        f"BRIDGE_PORT={bridge_p}",
        f"GATEWAY_PORT={gateway_p}",
        f"SESSION_DIR={d}/session",
        f"BRIDGE_LOG={d}/logs/bridge.log",
        f"GATEWAY_LOG={d}/logs/gateway.log",
        f"PRODUCT_FILE={d}/produto.md",
        "",
        "# WHATSAPP / BAILEYS",
        "WHATSAPP_ENABLED=false",
        f"WHATSAPP_MODE={whatsapp_mode}",
        "WHATSAPP_ALLOWED_USERS=*",
        "WHATSAPP_DM_POLICY=open",
        "WHATSAPP_GROUP_POLICY=open",
        # Política 'open' exige este opt-in explícito, senão o gateway se
        # recusa a subir ("Refusing to start: ... open policy without
        # allow-all opt-in").
        "WHATSAPP_ALLOW_ALL_USERS=true",
        f"WHATSAPP_OWNER_NUMBER={whatsapp_owner_number}",
        "",
        "# GATEWAY",
        f"HERMES_GATEWAY_BRIDGE_URL=http://127.0.0.1:{bridge_p}",
        "",
        "# AGENT",
        f"AGENT_MODEL={model}",
        f"AGENT_LANGUAGE={language}",
    ]

    if temperature is not None:
        env_lines.append(f"AGENT_TEMPERATURE={temperature}")

    # Campos de persona — armazenados no .env para permitir re-render no PUT
    env_lines += [
        "",
        "# PERSONA (usados para re-render do SOUL.md no PUT /agents/{id})",
        f"AGENT_NAME={name}",
        f"AGENT_DESCRIPTION={description}",
        f"AGENT_OBJECTIVE={objective}",
        f"AGENT_PERSONALITY={personality}",
        f"AGENT_INITIAL_PROMPT={initial_prompt}",
    ]

    # Gravar chave de API do provedor escolhido — se não vier no request,
    # herdar do .env global (senão o perfil nasce sem credencial nenhuma
    # para o provider configurado).
    provider_key_name = _provider_env_key(provider)
    if provider_api_key:
        env_lines.append(f"{provider_key_name}={provider_api_key}")
    elif provider_key_name in global_env:
        env_lines.append(f"{provider_key_name}={global_env[provider_key_name]}")

    # Propagar outras chaves do ambiente global (não duplicar a do provider)
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        if key in global_env and key != provider_key_name:
            env_lines.append(f"{key}={global_env[key]}")

    (d / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")

    # ── Phase 4.4: SOUL.md ────────────────────────────────────────────────────
    soul_content = _render_soul(
        name=name,
        description=description,
        objective=objective,
        personality=personality,
        language=language,
        initial_prompt=initial_prompt,
    )
    (d / "SOUL.md").write_text(soul_content, encoding="utf-8")

    # ── Phase 4.5: produto.md ─────────────────────────────────────────────────
    produto_content = _render_produto(name=name, description=description)
    (d / "produto.md").write_text(produto_content, encoding="utf-8")

    # ── Symlinks para skills e config globais ────────────────────────────────
    if SKILLS_DIR.exists():
        (d / "skills").symlink_to(SKILLS_DIR)

    # ── Plugin whatsapp-mixed (instalado globalmente + habilitado no perfil) ──
    _install_whatsapp_mixed_plugin(d)

    # ── Contato do dono espelhado a partir de WHATSAPP_OWNER_NUMBER ───────────
    if whatsapp_owner_number:
        from contacts import set_contact
        set_contact(d, whatsapp_owner_number, contact_type="owner")

    return _profile_dict(d)


def _install_whatsapp_mixed_plugin(d: Path) -> None:
    """
    Instala o plugin whatsapp-mixed e o habilita no config.yaml do perfil.
    Sempre instalado, mesmo que WHATSAPP_MODE != mixed — o plugin faz
    early-return e não interfere; assim, um PUT que troque o modo pra
    "mixed" depois já funciona sem precisar re-provisionar nada.

    O discovery de plugins do hermes-agent escaneia `HERMES_HOME/plugins/`
    (hermes_cli/plugins.py) — como cada gateway sobe com HERMES_HOME
    apontando para o diretório do perfil, o plugin é copiado para
    `<profile>/plugins/` e habilitado via `plugins.enabled` no config.yaml
    do perfil (plugins de usuário são opt-in por padrão).
    """
    src = Path(__file__).parent.parent / "templates" / "plugins" / "whatsapp-mixed"
    if not src.is_dir():
        return
    dest_root = d / "plugins"
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / "whatsapp-mixed"
    if not dest.exists():
        shutil.copytree(src, dest)

    _enable_plugin_in_config(d, "whatsapp-mixed")


def _enable_plugin_in_config(d: Path, plugin_name: str) -> None:
    """Adiciona `plugin_name` à lista `plugins.enabled` do config.yaml do perfil (idempotente)."""
    import yaml

    cfg_file = d / "config.yaml"
    cfg = {}
    if cfg_file.exists():
        try:
            cfg = yaml.safe_load(cfg_file.read_text()) or {}
        except Exception:
            cfg = {}

    plugins_cfg = cfg.get("plugins")
    if not isinstance(plugins_cfg, dict):
        plugins_cfg = {}
    enabled = plugins_cfg.get("enabled")
    if not isinstance(enabled, list):
        enabled = []
    if plugin_name not in enabled:
        enabled.append(plugin_name)
    plugins_cfg["enabled"] = enabled
    cfg["plugins"] = plugins_cfg

    cfg_file.write_text(yaml.dump(cfg, default_flow_style=False), encoding="utf-8")


def _profile_dict(d: Path) -> dict:
    from hermes_fs import profile_info
    return profile_info(d)
