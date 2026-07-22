"""
lifecycle.py — edição e deleção completa de perfis Hermes.
Reimplementa edit-profile e delete-profile em código determinístico,
SEM invocar LLM, agente Root ou qualquer canal de conversa.
"""

import os
import shutil
import time
from pathlib import Path

from hermes_fs import (
    load_env, read_soul, profile_info,
    safe_profile_path, stop_gateway, pid_alive, read_pid,
)

_KNOWLEDGE_MARKER_START = "## [CONSULTA DE CONHECIMENTO]"
_KNOWLEDGE_MARKER_END = "## [INSTRUÇÕES ADICIONAIS]"

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _read_config_provider(d: Path) -> str | None:
    """Lê o `provider` atual do config.yaml do perfil (fonte de verdade —
    não confundir com AGENT_PROVIDER, que nunca é gravado no .env)."""
    cfg_file = d / "config.yaml"
    if not cfg_file.exists():
        return None
    import yaml
    try:
        cfg = yaml.safe_load(cfg_file.read_text()) or {}
    except Exception:
        return None
    return cfg.get("provider")


# ─── Escrita atômica de .env ──────────────────────────────────────────────────

def _write_env(d: Path, env: dict[str, str]) -> None:
    """
    Atualiza o .env do perfil preservando comentários e ordem das linhas existentes.
    Chaves novas são adicionadas ao final. Escrita atômica via arquivo temporário.
    """
    envfile = d / ".env"
    lines = []
    remaining = dict(env)  # cópia — consumida conforme linhas são processadas

    if envfile.exists():
        for line in envfile.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                lines.append(line)
                continue
            if "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in remaining:
                    lines.append(f"{k}={remaining.pop(k)}")
                else:
                    lines.append(line)
            else:
                lines.append(line)

    # Chaves novas que não existiam no arquivo
    for k, v in remaining.items():
        lines.append(f"{k}={v}")

    tmp = envfile.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(envfile)  # atômico no Linux


# ─── Re-render do SOUL.md ─────────────────────────────────────────────────────

def _rerender_soul(d: Path, env: dict[str, str]) -> None:
    """
    Re-gera o SOUL.md a partir do template, preservando seções injetadas
    (CONSULTA DE CONHECIMENTO) que não fazem parte dos campos de persona.
    """
    tmpl = TEMPLATES_DIR / "SOUL.sdr.md"
    soul = tmpl.read_text(encoding="utf-8")

    replacements = {
        "{{NAME}}":           env.get("AGENT_NAME", ""),
        "{{DESCRIPTION}}":    env.get("AGENT_DESCRIPTION", ""),
        "{{OBJECTIVE}}":      env.get("AGENT_OBJECTIVE", ""),
        "{{PERSONALITY}}":    env.get("AGENT_PERSONALITY", ""),
        "{{LANGUAGE}}":       env.get("AGENT_LANGUAGE", "pt-BR"),
        "{{INITIAL_PROMPT}}": env.get("AGENT_INITIAL_PROMPT", ""),
    }
    for k, v in replacements.items():
        soul = soul.replace(k, v)

    # Preservar a seção de conhecimento do arquivo atual (se existir)
    knowledge_block = _extract_knowledge_block(d)
    if knowledge_block:
        soul = _inject_knowledge_block(soul, knowledge_block)

    tmp = (d / "SOUL.md").with_suffix(".tmp")
    tmp.write_text(soul, encoding="utf-8")
    tmp.replace(d / "SOUL.md")


def _extract_knowledge_block(d: Path) -> str:
    """Extrai o bloco de conhecimento do SOUL.md atual (se existir)."""
    soul = read_soul(d)
    if _KNOWLEDGE_MARKER_START not in soul:
        return ""
    after_start = soul.split(_KNOWLEDGE_MARKER_START, 1)[1]
    # Pega só até o próximo cabeçalho ## (exclusive)
    if _KNOWLEDGE_MARKER_END in after_start:
        block = after_start.split(_KNOWLEDGE_MARKER_END, 1)[0]
    else:
        block = after_start
    return block.strip()


def _inject_knowledge_block(soul: str, block: str) -> str:
    """
    Insere/substitui a seção de conhecimento no SOUL.
    A seção fica entre _KNOWLEDGE_MARKER_START e _KNOWLEDGE_MARKER_END.
    Se o template não tiver _KNOWLEDGE_MARKER_START, adiciona antes do END.
    """
    section = f"\n{_KNOWLEDGE_MARKER_START}\n{block}\n"
    if _KNOWLEDGE_MARKER_START in soul:
        before = soul.split(_KNOWLEDGE_MARKER_START, 1)[0]
        after_marker = soul.split(_KNOWLEDGE_MARKER_START, 1)[1]
        if _KNOWLEDGE_MARKER_END in after_marker:
            after = _KNOWLEDGE_MARKER_END + after_marker.split(_KNOWLEDGE_MARKER_END, 1)[1]
        else:
            after = ""
        return before.rstrip() + section + after
    elif _KNOWLEDGE_MARKER_END in soul:
        before, after = soul.split(_KNOWLEDGE_MARKER_END, 1)
        return before.rstrip() + section + _KNOWLEDGE_MARKER_END + after
    else:
        return soul.rstrip() + section


# ─── update_profile ──────────────────────────────────────────────────────────

def update_profile(
    profile_id: str,
    name: str | None = None,
    description: str | None = None,
    objective: str | None = None,
    personality: str | None = None,
    language: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    initial_prompt: str | None = None,
    provider: str | None = None,
    provider_api_key: str | None = None,
    whatsapp_mode: str | None = None,
    whatsapp_owner_number: str | None = None,
) -> dict:
    """
    Edita um perfil existente.
    - Campos de persona: re-renderiza o SOUL.md a partir do template com os valores atualizados.
    - model/language/temperature: atualiza o .env.
    - Se o gateway estiver rodando, faz restart escopado.
    """
    from provision import WHATSAPP_MODES
    if whatsapp_mode is not None and whatsapp_mode not in WHATSAPP_MODES:
        raise ValueError(f"whatsapp_mode inválido: '{whatsapp_mode}'. Use um de {WHATSAPP_MODES}.")
    d = safe_profile_path(profile_id)
    if not d:
        raise ValueError(f"Perfil '{profile_id}' não encontrado.")

    # Verificar e parar gateway se ativo
    was_running = False
    pid_file = d / "gateway.pid"
    pid = read_pid(pid_file) if pid_file.exists() else None
    if pid and pid_alive(pid):
        was_running = True
        stop_gateway(d)

    env = load_env(d)

    # Atualizar campos de persona no env (fonte de verdade para re-render)
    if name is not None:
        env["AGENT_NAME"] = name
    if description is not None:
        env["AGENT_DESCRIPTION"] = description
    if objective is not None:
        env["AGENT_OBJECTIVE"] = objective
    if personality is not None:
        env["AGENT_PERSONALITY"] = personality
    if language is not None:
        env["AGENT_LANGUAGE"] = language
    if initial_prompt is not None:
        env["AGENT_INITIAL_PROMPT"] = initial_prompt

    # Atualizar campos de runtime
    if model is not None:
        env["AGENT_MODEL"] = model
    if temperature is not None:
        env["AGENT_TEMPERATURE"] = str(temperature)
    if provider_api_key is not None:
        from provision import _provider_env_key
        current_provider = provider or _read_config_provider(d) or "anthropic"
        key_name = _provider_env_key(current_provider)
        env[key_name] = provider_api_key
    elif provider is not None:
        # Provider mudou sem key nova — herdar do .env global, senão o
        # perfil fica com config.yaml apontando pra um provider sem
        # credencial nenhuma (gateway falha com "Unknown provider").
        from provision import _provider_env_key, _global_env_keys
        key_name = _provider_env_key(provider)
        if key_name not in env:
            global_env = _global_env_keys()
            if key_name in global_env:
                env[key_name] = global_env[key_name]
    if whatsapp_mode is not None:
        env["WHATSAPP_MODE"] = whatsapp_mode
    if whatsapp_owner_number is not None:
        env["WHATSAPP_OWNER_NUMBER"] = whatsapp_owner_number

    _write_env(d, env)
    _rerender_soul(d, env)

    # Atualizar config.yaml se o provider mudar
    if provider is not None:
        import yaml
        cfg_file = d / "config.yaml"
        if cfg_file.exists():
            try:
                cfg = yaml.safe_load(cfg_file.read_text()) or {}
            except Exception:
                cfg = {}
        else:
            cfg = {}
        cfg["provider"] = provider
        cfg_file.write_text(yaml.dump(cfg, default_flow_style=False), encoding="utf-8")

    # Garante o plugin instalado (perfis criados antes desta feature não o têm)
    # e espelha o contato do dono se o número mudou.
    from provision import _install_whatsapp_mixed_plugin
    _install_whatsapp_mixed_plugin(d)
    if whatsapp_owner_number:
        from contacts import set_contact
        set_contact(d, whatsapp_owner_number, contact_type="owner")

    if was_running:
        from hermes_fs import start_gateway
        start_gateway(d)

    return profile_info(d)


# ─── inject_knowledge_rule ────────────────────────────────────────────────────

def inject_knowledge_rule(d: Path, filename: str) -> None:
    """
    Injeta/atualiza a seção de conhecimento no SOUL.md listando todos os
    arquivos presentes em knowledge/. Idempotente — pode ser chamada várias vezes.
    """
    kdir = d / "knowledge"
    files = sorted(f.name for f in kdir.iterdir() if f.is_file()) if kdir.is_dir() else []
    if not files:
        return

    # Caminho absoluto — o processo do gateway não roda com cwd na pasta do
    # perfil (start_gateway usa a pasta do bridge do WhatsApp como cwd), então
    # um caminho relativo tipo `knowledge/arquivo.md` não resolve.
    file_list = "\n".join(f"- `{kdir / f}`" for f in files)
    block = (
        "Antes de responder perguntas sobre produtos, serviços, procedimentos ou "
        "qualquer informação específica do negócio, consulte os arquivos abaixo "
        "(caminhos absolutos).\n\n"
        f"Arquivos disponíveis:\n{file_list}"
    )

    soul = read_soul(d)
    if not soul:
        return

    new_soul = _inject_knowledge_block(soul, block)
    tmp = (d / "SOUL.md").with_suffix(".tmp")
    tmp.write_text(new_soul, encoding="utf-8")
    tmp.replace(d / "SOUL.md")


# ─── delete_profile ──────────────────────────────────────────────────────────

def delete_profile(profile_id: str) -> None:
    """
    Remove completamente um perfil:
    1. Para o gateway por PID (TERM→KILL)
    2. Para o bridge por PID (se bridge.pid existir)
    3. Remove o diretório do perfil

    Nota: `default-profile` é protegido e não pode ser deletado.
    """
    if profile_id == "default-profile":
        raise ValueError("default-profile é protegido e não pode ser deletado.")
    d = safe_profile_path(profile_id)
    if not d:
        raise ValueError(f"Perfil '{profile_id}' não encontrado.")

    stop_gateway(d)

    bridge_pid_file = d / "bridge.pid"
    if bridge_pid_file.exists():
        pid = read_pid(bridge_pid_file)
        if pid and pid_alive(pid):
            try:
                os.kill(pid, 15)
            except OSError:
                pass
            for _ in range(8):
                time.sleep(0.25)
                if not pid_alive(pid):
                    break
            if pid_alive(pid):
                try:
                    os.kill(pid, 9)
                except OSError:
                    pass
                time.sleep(0.3)

    shutil.rmtree(d)
