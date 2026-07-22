"""
produto.py — fonte única do contexto de negócio de um perfil (produto.yaml).

Guarda em profiles/<agent_id>/produto.yaml. Substitui o antigo produto.md: além
do texto de negócio (identidade, pagamento, conhecimento livre), carrega a
configuração ESTRUTURADA da agenda (expediente, serviços com preço/duração,
profissionais/escala, lembretes, políticas) que o motor de disponibilidade lê
para calcular vagas paralelas.

É o mesmo módulo usado pela aba "Produto" do dashboard e pela skill `produto`
(comandos $PRODUTO que o Número Home dispara por chat) — então painel e agente
nunca divergem de schema. TODA escrita passa por aqui: leitura → mutação →
validação → escrita ATÔMICA (tmp + os.replace), pra config nunca ficar
YAML quebrado (ela porteira todos os agendamentos).
"""

import os
import tempfile
from pathlib import Path

import yaml

DIAS = ("seg", "ter", "qua", "qui", "sex", "sab", "dom")
CATEGORIAS_SUGERIDAS = ("Cabelo", "Unhas", "Estética", "Outros")


def _path(d: Path) -> Path:
    return d / "produto.yaml"


# ----------------------------------------------------------------------------- #
# Defaults / esqueleto
# ----------------------------------------------------------------------------- #

def _skeleton() -> dict:
    return {
        "schema_version": 1,
        "negocio": {"nome": "", "tipo": "", "cidade": "", "endereco": "",
                    "whatsapp": "", "instagram": []},
        "agenda": {
            "configurado": False,
            "timezone": "America/Sao_Paulo",
            "slot_min": 60,
            "expediente": {d: None for d in DIAS},
            "lembretes": {"confirmacao": {"dia": "D-1", "hora": "13:00"},
                          "aviso": {"offset_min": -60}},
            "politicas": {"antecedencia_min_agendamento_h": 0,
                          "cancelamento_antecedencia_h": 0},
        },
        "categorias": [],
        "servicos": [],
        "profissionais": [],
        "pagamento": {"formas": [], "politica_desconto": ""},
        "conhecimento": [],
    }


def _merge_defaults(data: dict) -> dict:
    """Garante que chaves esperadas existem, sem sobrescrever o que veio."""
    base = _skeleton()

    def deep(dst, src):
        for k, v in src.items():
            if isinstance(v, dict):
                dst[k] = deep(dst.get(k) if isinstance(dst.get(k), dict) else {}, v)
            elif k not in dst or dst[k] is None and not isinstance(v, list):
                dst.setdefault(k, v)
        return dst

    data = data or {}
    for k, v in base.items():
        if k not in data:
            data[k] = v
        elif isinstance(v, dict):
            data[k] = deep(data[k] if isinstance(data[k], dict) else {}, v)
    return data


# ----------------------------------------------------------------------------- #
# Load / save
# ----------------------------------------------------------------------------- #

def load(d: Path) -> dict:
    p = _path(d)
    if not p.exists():
        return _skeleton()
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data = _merge_defaults(data)
    # Categorias não são fixas (nem todo negócio é salão). Se a config ainda não
    # tem a lista, deriva das categorias já usadas nos serviços (ordem preservada).
    if not data.get("categorias"):
        seen, cats = set(), []
        for s in data.get("servicos") or []:
            c = (s.get("categoria") or "").strip()
            if c and c.lower() not in seen:
                seen.add(c.lower())
                cats.append(c)
        data["categorias"] = cats
    return data


def _atomic_save(d: Path, data: dict) -> None:
    """Valida e grava de forma atômica (tmp no mesmo dir + os.replace)."""
    errs = validate(data)
    if errs:
        raise ValueError("produto.yaml inválido: " + "; ".join(errs))
    p = _path(d)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".produto.", suffix=".yaml")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False,
                           default_flow_style=False)
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# ----------------------------------------------------------------------------- #
# Validação
# ----------------------------------------------------------------------------- #

def _parse_faixa(faixa):
    """'09:00-19:00' -> ((9,0),(19,0)) ou None se inválida."""
    try:
        ini, fim = faixa.split("-")
        h1, m1 = (int(x) for x in ini.strip().split(":"))
        h2, m2 = (int(x) for x in fim.strip().split(":"))
        if not (0 <= h1 < 24 and 0 <= h2 <= 24 and 0 <= m1 < 60 and 0 <= m2 < 60):
            return None
        if (h1, m1) >= (h2, m2):
            return None
        return ((h1, m1), (h2, m2))
    except (ValueError, AttributeError):
        return None


def validate(data: dict) -> list[str]:
    errs = []
    ag = data.get("agenda", {})

    slot = ag.get("slot_min")
    if not isinstance(slot, int) or slot <= 0 or 60 % slot and slot % 60:
        errs.append(f"agenda.slot_min deve ser inteiro divisor/múltiplo de 60 (got {slot!r})")

    for dia, faixa in (ag.get("expediente") or {}).items():
        if dia not in DIAS:
            errs.append(f"expediente: dia inválido '{dia}'")
        if faixa is not None and _parse_faixa(faixa) is None:
            errs.append(f"expediente[{dia}]: faixa inválida '{faixa}' (use 'HH:MM-HH:MM')")

    nomes_serv = set()
    for s in data.get("servicos") or []:
        nome = (s.get("nome") or "").strip()
        if not nome:
            errs.append("serviço sem nome")
            continue
        if nome.lower() in nomes_serv:
            errs.append(f"serviço duplicado: '{nome}'")
        nomes_serv.add(nome.lower())
        if not isinstance(s.get("preco"), (int, float)) or s["preco"] < 0:
            errs.append(f"serviço '{nome}': preço inválido")
        if not isinstance(s.get("duracao_min"), int) or s["duracao_min"] <= 0:
            errs.append(f"serviço '{nome}': duracao_min inválida")

    for pf in data.get("profissionais") or []:
        nome = (pf.get("nome") or "").strip()
        if not nome:
            errs.append("profissional sem nome")
            continue
        for dia in pf.get("dias") or []:
            if dia not in DIAS:
                errs.append(f"profissional '{nome}': dia inválido '{dia}'")
        if _parse_faixa(pf.get("horario") or "") is None:
            errs.append(f"profissional '{nome}': horário inválido '{pf.get('horario')}'")
        for sv in pf.get("servicos") or []:
            if sv.strip().lower() not in nomes_serv:
                errs.append(f"profissional '{nome}': serviço desconhecido '{sv}'")
    return errs


# ----------------------------------------------------------------------------- #
# Helpers de leitura (usados pelo motor de disponibilidade)
# ----------------------------------------------------------------------------- #

def service_names(data: dict) -> list[str]:
    return [s["nome"] for s in data.get("servicos") or []]


def find_service(data: dict, nome: str) -> dict | None:
    n = (nome or "").strip().lower()
    for s in data.get("servicos") or []:
        if s["nome"].strip().lower() == n:
            return s
    return None


def expediente_do_dia(data: dict, dia: str):
    """Retorna ((h1,m1),(h2,m2)) do expediente do dia, ou None se fechado."""
    faixa = (data.get("agenda", {}).get("expediente") or {}).get(dia)
    return _parse_faixa(faixa) if faixa else None


def _hhmm_dentro(faixa_parsed, h, m) -> bool:
    (h1, m1), (h2, m2) = faixa_parsed
    return (h1, m1) <= (h, m) < (h2, m2)


def profissionais_no_slot(data: dict, dia: str, h: int, m: int, servico: str | None = None) -> list[str]:
    """Profissionais que trabalham nesse dia/horário E fazem o serviço
    (servicos vazio = faz tudo). É a CAPACIDADE do slot para aquele serviço."""
    out = []
    serv_l = servico.strip().lower() if servico else None
    for pf in data.get("profissionais") or []:
        if dia not in (pf.get("dias") or []):
            continue
        faixa = _parse_faixa(pf.get("horario") or "")
        if not faixa or not _hhmm_dentro(faixa, h, m):
            continue
        faz = [x.strip().lower() for x in (pf.get("servicos") or [])]
        if serv_l and faz and serv_l not in faz:
            continue
        out.append(pf["nome"])
    return out


# ----------------------------------------------------------------------------- #
# Mutações (cada uma: load → muta → save atômico; devolve o novo estado)
# ----------------------------------------------------------------------------- #

def _save(d, data):
    _atomic_save(d, data)
    return data


def set_price(d: Path, nome: str, preco: float) -> dict:
    data = load(d)
    s = find_service(data, nome)
    if not s:
        raise ValueError(f"Serviço não encontrado: '{nome}'. Existentes: {service_names(data)}")
    s["preco"] = round(float(preco), 2)
    return _save(d, data)


def set_duration(d: Path, nome: str, minutos: int) -> dict:
    data = load(d)
    s = find_service(data, nome)
    if not s:
        raise ValueError(f"Serviço não encontrado: '{nome}'. Existentes: {service_names(data)}")
    s["duracao_min"] = int(minutos)
    return _save(d, data)


def add_service(d: Path, nome: str, categoria: str, preco: float, duracao_min: int) -> dict:
    data = load(d)
    if find_service(data, nome):
        raise ValueError(f"Serviço já existe: '{nome}' (use set-price/set-duration)")
    data.setdefault("servicos", []).append({
        "nome": nome.strip(), "categoria": categoria.strip() or "Outros",
        "preco": round(float(preco), 2), "duracao_min": int(duracao_min)})
    return _save(d, data)


def remove_service(d: Path, nome: str) -> dict:
    data = load(d)
    if not find_service(data, nome):
        raise ValueError(f"Serviço não encontrado: '{nome}'")
    n = nome.strip().lower()
    data["servicos"] = [s for s in data["servicos"] if s["nome"].strip().lower() != n]
    for pf in data.get("profissionais") or []:
        pf["servicos"] = [x for x in (pf.get("servicos") or []) if x.strip().lower() != n]
    return _save(d, data)


def add_category(d: Path, nome: str) -> dict:
    data = load(d)
    cats = data.setdefault("categorias", [])
    if nome.strip().lower() in [c.lower() for c in cats]:
        raise ValueError(f"Categoria já existe: '{nome}'")
    cats.append(nome.strip())
    return _save(d, data)


def remove_category(d: Path, nome: str) -> dict:
    data = load(d)
    n = nome.strip().lower()
    data["categorias"] = [c for c in (data.get("categorias") or []) if c.strip().lower() != n]
    return _save(d, data)


def set_hours(d: Path, dia: str, faixa: str) -> dict:
    if dia not in DIAS:
        raise ValueError(f"Dia inválido: '{dia}'. Use um de {DIAS}")
    if _parse_faixa(faixa) is None:
        raise ValueError(f"Faixa inválida: '{faixa}'. Use 'HH:MM-HH:MM'")
    data = load(d)
    data["agenda"]["expediente"][dia] = faixa
    return _save(d, data)


def close_day(d: Path, dia: str) -> dict:
    if dia not in DIAS:
        raise ValueError(f"Dia inválido: '{dia}'. Use um de {DIAS}")
    data = load(d)
    data["agenda"]["expediente"][dia] = None
    return _save(d, data)


def _find_prof(data, nome):
    n = (nome or "").strip().lower()
    for pf in data.get("profissionais") or []:
        if pf["nome"].strip().lower() == n:
            return pf
    return None


def add_professional(d: Path, nome: str, dias: list[str], horario: str, servicos: list[str] | None = None) -> dict:
    data = load(d)
    if _find_prof(data, nome):
        raise ValueError(f"Profissional já existe: '{nome}'")
    data.setdefault("profissionais", []).append({
        "nome": nome.strip(), "dias": list(dias),
        "horario": horario, "servicos": list(servicos or [])})
    return _save(d, data)


def remove_professional(d: Path, nome: str) -> dict:
    data = load(d)
    if not _find_prof(data, nome):
        raise ValueError(f"Profissional não encontrado: '{nome}'")
    n = nome.strip().lower()
    data["profissionais"] = [p for p in data["profissionais"] if p["nome"].strip().lower() != n]
    return _save(d, data)


def set_professional_days(d: Path, nome: str, dias: list[str]) -> dict:
    data = load(d)
    pf = _find_prof(data, nome)
    if not pf:
        raise ValueError(f"Profissional não encontrado: '{nome}'")
    pf["dias"] = list(dias)
    return _save(d, data)


def set_professional_hours(d: Path, nome: str, horario: str) -> dict:
    data = load(d)
    pf = _find_prof(data, nome)
    if not pf:
        raise ValueError(f"Profissional não encontrado: '{nome}'")
    pf["horario"] = horario
    return _save(d, data)


def set_professional_services(d: Path, nome: str, servicos: list[str]) -> dict:
    data = load(d)
    pf = _find_prof(data, nome)
    if not pf:
        raise ValueError(f"Profissional não encontrado: '{nome}'")
    pf["servicos"] = list(servicos)
    return _save(d, data)


def add_fact(d: Path, texto: str) -> dict:
    data = load(d)
    data.setdefault("conhecimento", []).append(texto.strip())
    return _save(d, data)


def update_fact(d: Path, idx: int, texto: str) -> dict:
    data = load(d)
    facts = data.get("conhecimento") or []
    if not (0 <= idx < len(facts)):
        raise ValueError(f"Fato #{idx} não existe (há {len(facts)})")
    facts[idx] = texto.strip()
    return _save(d, data)


def remove_fact(d: Path, idx: int) -> dict:
    data = load(d)
    facts = data.get("conhecimento") or []
    if not (0 <= idx < len(facts)):
        raise ValueError(f"Fato #{idx} não existe (há {len(facts)})")
    facts.pop(idx)
    return _save(d, data)
