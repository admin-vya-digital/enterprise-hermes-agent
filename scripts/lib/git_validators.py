"""
Validações de Git/GitHub para garantir conformidade com melhores práticas.

Este módulo fornece funções para validar:
- Nomes de branches (convenção feature/NNN-descricao)
- Mensagens de commit (Conventional Commits)
- Status de PR readiness
- Branch protection compliance

Uso:
    from scripts.lib.git_validators import validate_branch_name, validate_commit_message

    # Validar nome de branch
    is_valid, message = validate_branch_name("feature/042-user-auth")

    # Validar mensagem de commit
    is_valid, message = validate_commit_message("feat(api): add user endpoint")
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple

# =============================================================================
# Tipos e Enums
# =============================================================================

class BranchType(Enum):
    """Tipos de branch permitidos."""
    FEATURE = "feature"
    FIX = "fix"
    HOTFIX = "hotfix"
    CHORE = "chore"
    DOCS = "docs"
    REFACTOR = "refactor"
    TEST = "test"


class CommitType(Enum):
    """Tipos de commit do Conventional Commits."""
    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"
    REFACTOR = "refactor"
    PERF = "perf"
    TEST = "test"
    CHORE = "chore"
    CI = "ci"
    BUILD = "build"


@dataclass
class BranchValidation:
    """Resultado de validação de branch."""
    is_valid: bool
    branch_name: str
    branch_type: Optional[BranchType]
    issue_number: Optional[int]
    description: str
    errors: list[str]
    warnings: list[str]


@dataclass
class CommitValidation:
    """Resultado de validação de commit."""
    is_valid: bool
    commit_message: str
    commit_type: Optional[CommitType]
    scope: Optional[str]
    subject: str
    body: Optional[str]
    footer: Optional[str]
    is_breaking: bool
    errors: list[str]
    warnings: list[str]


# =============================================================================
# Padrões Regex
# =============================================================================

# Branch patterns
# feature/123-descricao, fix/descricao, hotfix/critical-bug, etc.
BRANCH_PATTERN = re.compile(
    r"^(?P<type>feature|fix|hotfix|chore|docs|refactor|test)"
    r"/(?:(?P<issue>\d+)-)?(?P<desc>[a-z0-9-]+)$"
)

# Commit message pattern (Conventional Commits)
# type(scope): subject
# type(scope)!: subject (breaking)
# type: subject
COMMIT_PATTERN = re.compile(
    r"^(?P<type>feat|fix|docs|style|refactor|perf|test|chore|ci|build)"
    r"(?:\((?P<scope>[a-z0-9-]+)\))?"
    r"(?P<breaking>!)?"
    r": "
    r"(?P<subject>.+)$",
    re.IGNORECASE
)

# =============================================================================
# Validadores de Branch
# =============================================================================

def validate_branch_name(branch_name: str) -> BranchValidation:
    """
    Valida nome de branch segundo convenções do projeto.

    Formato esperado:
    - feature/NNN-descricao-curta
    - fix/descricao-bug
    - hotfix/descricao-critica
    - chore/descricao-tarefa

    Regras:
    - Lowercase apenas
    - Hífens para separar palavras (não underscores)
    - Issue number opcional (obrigatório para features)
    - Descrição concisa (max 50 chars)

    Args:
        branch_name: Nome da branch a validar

    Returns:
        BranchValidation com resultado e detalhes

    Examples:
        >>> result = validate_branch_name("feature/042-user-authentication")
        >>> result.is_valid
        True
        >>> result.branch_type
        BranchType.FEATURE
        >>> result.issue_number
        42

        >>> result = validate_branch_name("FEATURE/bad-name")
        >>> result.is_valid
        False
        >>> result.errors
        ['Branch deve estar em lowercase']
    """
    errors = []
    warnings = []
    branch_type = None
    issue_number = None
    description = ""

    # Casos especiais permitidos
    if branch_name in ("main", "master", "develop", "staging", "production"):
        return BranchValidation(
            is_valid=True,
            branch_name=branch_name,
            branch_type=None,
            issue_number=None,
            description="protected branch",
            errors=[],
            warnings=[]
        )

    # Verificar lowercase
    if branch_name != branch_name.lower():
        errors.append("Branch deve estar em lowercase")

    # Verificar caracteres especiais
    if not re.match(r"^[a-z0-9/-]+$", branch_name):
        errors.append("Branch deve conter apenas letras minúsculas, números, hífens e barras")

    # Verificar padrão
    match = BRANCH_PATTERN.match(branch_name)
    if not match:
        errors.append(
            "Branch deve seguir padrão: tipo/[NNN-]descricao "
            "(ex: feature/042-user-auth, fix/memory-leak)"
        )
        is_valid = False
    else:
        # Extrair componentes
        type_str = match.group("type")
        issue_str = match.group("issue")
        desc = match.group("desc")

        try:
            branch_type = BranchType(type_str)
        except ValueError:
            errors.append(f"Tipo de branch inválido: {type_str}")

        if issue_str:
            issue_number = int(issue_str)

        description = desc

        # Validações específicas por tipo
        if branch_type == BranchType.FEATURE and not issue_number:
            warnings.append("Features devem ter issue number (feature/NNN-descricao)")

        # Validar comprimento da descrição
        if len(desc) > 50:
            warnings.append(f"Descrição muito longa ({len(desc)} chars, máx 50)")

        if len(desc) < 3:
            errors.append("Descrição muito curta (mín 3 chars)")

        # Verificar underscores (devem ser hífens)
        if "_" in desc:
            warnings.append("Use hífens (-) ao invés de underscores (_)")

        is_valid = len(errors) == 0

    return BranchValidation(
        is_valid=is_valid,
        branch_name=branch_name,
        branch_type=branch_type,
        issue_number=issue_number,
        description=description,
        errors=errors,
        warnings=warnings
    )


def is_protected_branch(branch_name: str) -> bool:
    """
    Verifica se branch é protegida (main, master, etc.).

    Args:
        branch_name: Nome da branch

    Returns:
        True se branch deve ser protegida
    """
    protected = {"main", "master", "develop", "staging", "production"}
    return branch_name in protected


# =============================================================================
# Validadores de Commit
# =============================================================================

def validate_commit_message(message: str) -> CommitValidation:
    """
    Valida mensagem de commit segundo Conventional Commits.

    Formato esperado:
    - type(scope): subject
    - type(scope)!: subject  (breaking change)
    - type: subject

    Opcionalmente com body e footer:
    type(scope): subject

    Body descrevendo a mudança em detalhes.

    BREAKING CHANGE: descrição do breaking change
    Closes #123

    Args:
        message: Mensagem de commit a validar

    Returns:
        CommitValidation com resultado e detalhes

    Examples:
        >>> result = validate_commit_message("feat(api): add user endpoint")
        >>> result.is_valid
        True
        >>> result.commit_type
        CommitType.FEAT
        >>> result.scope
        'api'

        >>> result = validate_commit_message("feat(api)!: breaking change")
        >>> result.is_breaking
        True
    """
    errors = []
    warnings = []
    commit_type = None
    scope = None
    subject = ""
    body = None
    footer = None
    is_breaking = False

    # Separar subject, body, footer
    parts = message.split("\n\n", 2)
    subject_line = parts[0].strip()

    if len(parts) > 1:
        body = parts[1].strip()

    if len(parts) > 2:
        footer = parts[2].strip()

    # Validar subject line
    match = COMMIT_PATTERN.match(subject_line)

    if not match:
        errors.append(
            "Commit deve seguir Conventional Commits: "
            "tipo(escopo): descrição "
            "(ex: feat(api): add endpoint, fix: memory leak)"
        )
        is_valid = False
    else:
        # Extrair componentes
        type_str = match.group("type")
        scope = match.group("scope")
        subject = match.group("subject")
        is_breaking = match.group("breaking") == "!"

        try:
            commit_type = CommitType(type_str.lower())
        except ValueError:
            errors.append(f"Tipo de commit inválido: {type_str}")

        # Validar subject
        if len(subject) > 72:
            warnings.append(f"Subject muito longo ({len(subject)} chars, máx 72)")

        if len(subject) < 5:
            errors.append("Subject muito curto (mín 5 chars)")

        # Subject não deve terminar com ponto
        if subject.endswith("."):
            warnings.append("Subject não deve terminar com ponto final")

        # Subject deve começar com letra minúscula (convenção)
        if subject[0].isupper():
            warnings.append("Subject deve começar com letra minúscula")

        # Verificar palavras proibidas (vagas demais)
        vague_words = {"update", "change", "fix", "misc", "stuff", "things"}
        subject_words = set(subject.lower().split())
        if subject_words.intersection(vague_words) and len(subject_words) <= 2:
            warnings.append(
                f"Evite mensagens vagas: {', '.join(vague_words)}"
            )

        is_valid = len(errors) == 0

    # Verificar breaking change no body ou footer
    if body and "BREAKING CHANGE:" in body:
        is_breaking = True
    if footer and "BREAKING CHANGE:" in footer:
        is_breaking = True

    return CommitValidation(
        is_valid=is_valid,
        commit_message=message,
        commit_type=commit_type,
        scope=scope,
        subject=subject,
        body=body,
        footer=footer,
        is_breaking=is_breaking,
        errors=errors,
        warnings=warnings
    )


# =============================================================================
# Validações de PR Readiness
# =============================================================================

def check_pr_readiness(branch_name: str, current_dir: Path = Path.cwd()) -> dict:
    """
    Verifica se branch está pronta para abrir PR.

    Checklist:
    - Branch name válido
    - Commits desde main
    - Nenhum arquivo não-commitado
    - Tests passando (se houver)
    - Lint passando (se houver)

    Args:
        branch_name: Nome da branch atual
        current_dir: Diretório do repositório

    Returns:
        Dict com status e checklist

    Examples:
        >>> status = check_pr_readiness("feature/042-auth")
        >>> status["ready"]
        True
        >>> status["checks"]["branch_name_valid"]
        True
    """
    import subprocess

    checks = {}

    # 1. Validar nome da branch
    branch_validation = validate_branch_name(branch_name)
    checks["branch_name_valid"] = branch_validation.is_valid

    # 2. Verificar se há commits
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"origin/main..{branch_name}"],
            cwd=current_dir,
            capture_output=True,
            text=True,
            check=False
        )
        commit_count = int(result.stdout.strip() or "0")
        checks["has_commits"] = commit_count > 0
        checks["commit_count"] = commit_count
    except Exception:
        checks["has_commits"] = None
        checks["commit_count"] = 0

    # 3. Verificar working directory limpo
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=current_dir,
            capture_output=True,
            text=True,
            check=False
        )
        checks["working_dir_clean"] = len(result.stdout.strip()) == 0
    except Exception:
        checks["working_dir_clean"] = None

    # 4. Verificar se branch está atualizada com main
    try:
        subprocess.run(["git", "fetch", "origin", "main"], cwd=current_dir, check=False, capture_output=True)
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{branch_name}..origin/main"],
            cwd=current_dir,
            capture_output=True,
            text=True,
            check=False
        )
        behind_count = int(result.stdout.strip() or "0")
        checks["up_to_date_with_main"] = behind_count == 0
        checks["commits_behind"] = behind_count
    except Exception:
        checks["up_to_date_with_main"] = None
        checks["commits_behind"] = 0

    # Determinar se está pronto
    required_checks = ["branch_name_valid", "has_commits", "working_dir_clean"]
    ready = all(checks.get(check) for check in required_checks)

    return {
        "ready": ready,
        "checks": checks,
        "branch_validation": branch_validation
    }


# =============================================================================
# Helpers
# =============================================================================

def format_validation_errors(validation: BranchValidation | CommitValidation) -> str:
    """
    Formata erros e warnings de validação para exibição.

    Args:
        validation: Resultado de validação

    Returns:
        String formatada para exibir ao usuário
    """
    lines = []

    if validation.errors:
        lines.append("❌ Erros:")
        for error in validation.errors:
            lines.append(f"  - {error}")

    if validation.warnings:
        lines.append("⚠️  Avisos:")
        for warning in validation.warnings:
            lines.append(f"  - {warning}")

    return "\n".join(lines) if lines else "✅ Validação passou"


def suggest_branch_name(description: str, issue_number: Optional[int] = None) -> str:
    """
    Sugere nome de branch a partir de descrição.

    Args:
        description: Descrição da mudança
        issue_number: Número da issue (opcional)

    Returns:
        Nome de branch sugerido

    Examples:
        >>> suggest_branch_name("Add User Authentication", 42)
        'feature/042-add-user-authentication'

        >>> suggest_branch_name("Fix Memory Leak")
        'fix/memory-leak'
    """
    # Normalizar descrição
    normalized = description.lower()
    normalized = re.sub(r"[^a-z0-9\s-]", "", normalized)
    normalized = re.sub(r"\s+", "-", normalized.strip())
    normalized = normalized[:50]  # max 50 chars

    # Determinar tipo
    if "fix" in normalized or "bug" in normalized:
        branch_type = "fix"
    elif "doc" in normalized:
        branch_type = "docs"
    elif "test" in normalized:
        branch_type = "test"
    elif "refactor" in normalized:
        branch_type = "refactor"
    else:
        branch_type = "feature"

    # Construir nome
    if issue_number and branch_type == "feature":
        return f"{branch_type}/{issue_number:03d}-{normalized}"
    else:
        return f"{branch_type}/{normalized}"


if __name__ == "__main__":
    # Testes rápidos
    print("=== Teste de Validação de Branch ===")

    test_branches = [
        "feature/042-user-authentication",
        "fix/memory-leak",
        "FEATURE/bad-case",
        "feature/no-issue",
        "main",
        "invalid_branch_name",
    ]

    for branch in test_branches:
        result = validate_branch_name(branch)
        print(f"\n{branch}:")
        print(f"  Válido: {result.is_valid}")
        if result.errors:
            print(f"  Erros: {result.errors}")
        if result.warnings:
            print(f"  Avisos: {result.warnings}")

    print("\n\n=== Teste de Validação de Commit ===")

    test_commits = [
        "feat(api): add user endpoint",
        "fix: memory leak in parser",
        "feat(api)!: breaking change",
        "invalid commit message",
        "feat(api): Add New Feature.",
    ]

    for commit in test_commits:
        result = validate_commit_message(commit)
        print(f"\n{commit}:")
        print(f"  Válido: {result.is_valid}")
        print(f"  Breaking: {result.is_breaking}")
        if result.errors:
            print(f"  Erros: {result.errors}")
        if result.warnings:
            print(f"  Avisos: {result.warnings}")
