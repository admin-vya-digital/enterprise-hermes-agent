#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31.0",
#   "rich>=13.7",
# ]
# ///
"""
Setup GitHub Branch Protection

Configura proteção de branches via GitHub API.

Requisitos:
  - Token GitHub com permissões: repo (full)
  - Variável de ambiente: GITHUB_TOKEN

Uso:
  # Usando token de ambiente
  export GITHUB_TOKEN=ghp_xxxxx
  python scripts/setup-branch-protection.py owner/repo

  # Especificando token
  python scripts/setup-branch-protection.py owner/repo --token ghp_xxxxx

  # Nível personalizado
  python scripts/setup-branch-protection.py owner/repo --level maximum

  # Dry run (apenas mostrar configuração)
  python scripts/setup-branch-protection.py owner/repo --dry-run
"""

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any

try:
    import requests
    from rich.console import Console
    from rich.table import Table
except ImportError:
    print("❌ Dependências faltando. Instale com:")
    print("   pip install requests rich")
    sys.exit(1)


console = Console()


@dataclass
class BranchProtectionConfig:
    """Configuração de proteção de branch."""
    level: str
    require_pull_request: bool = True
    required_approving_review_count: int = 1
    dismiss_stale_reviews: bool = False
    require_code_owner_reviews: bool = False
    require_last_push_approval: bool = False
    required_status_checks: list[str] = None
    strict_status_checks: bool = True
    enforce_admins: bool = False
    allow_force_pushes: bool = False
    allow_deletions: bool = False
    block_creations: bool = False
    required_conversation_resolution: bool = False
    lock_branch: bool = False
    allow_fork_syncing: bool = True
    required_signatures: bool = False
    required_linear_history: bool = False


# Níveis de proteção pré-configurados
PROTECTION_LEVELS = {
    'minimum': BranchProtectionConfig(
        level='minimum',
        require_pull_request=True,
        required_approving_review_count=1,
        dismiss_stale_reviews=False,
        require_code_owner_reviews=False,
        enforce_admins=False,
        required_status_checks=['build', 'test'],
        strict_status_checks=True,
        allow_force_pushes=False,
        allow_deletions=False,
    ),
    'recommended': BranchProtectionConfig(
        level='recommended',
        require_pull_request=True,
        required_approving_review_count=1,
        dismiss_stale_reviews=True,
        require_code_owner_reviews=True,
        enforce_admins=True,
        required_status_checks=['build', 'test', 'lint', 'validate-git'],
        strict_status_checks=True,
        allow_force_pushes=False,
        allow_deletions=False,
        required_conversation_resolution=True,
    ),
    'maximum': BranchProtectionConfig(
        level='maximum',
        require_pull_request=True,
        required_approving_review_count=2,
        dismiss_stale_reviews=True,
        require_code_owner_reviews=True,
        require_last_push_approval=True,
        enforce_admins=True,
        required_status_checks=['build', 'test', 'lint', 'validate-git', 'security-scan'],
        strict_status_checks=True,
        allow_force_pushes=False,
        allow_deletions=False,
        required_conversation_resolution=True,
        required_signatures=True,
        required_linear_history=True,
    ),
}


def build_protection_payload(config: BranchProtectionConfig) -> dict[str, Any]:
    """Constrói payload para API do GitHub."""
    payload = {
        "required_status_checks": None,
        "enforce_admins": config.enforce_admins,
        "required_pull_request_reviews": None,
        "restrictions": None,  # Null = sem restrições de quem pode push
        "allow_force_pushes": config.allow_force_pushes,
        "allow_deletions": config.allow_deletions,
        "block_creations": config.block_creations,
        "required_conversation_resolution": config.required_conversation_resolution,
        "lock_branch": config.lock_branch,
        "allow_fork_syncing": config.allow_fork_syncing,
    }

    # Status checks
    if config.required_status_checks:
        payload["required_status_checks"] = {
            "strict": config.strict_status_checks,
            "checks": [{"context": check} for check in config.required_status_checks],
        }

    # Pull request reviews
    if config.require_pull_request:
        payload["required_pull_request_reviews"] = {
            "dismissal_restrictions": {},
            "dismiss_stale_reviews": config.dismiss_stale_reviews,
            "require_code_owner_reviews": config.require_code_owner_reviews,
            "required_approving_review_count": config.required_approving_review_count,
            "require_last_push_approval": config.require_last_push_approval,
        }

    # Configurações adicionais (não via branch protection, mas via separate API)
    # required_signatures - via /repos/{owner}/{repo}/branches/{branch}/protection/required_signatures
    # required_linear_history - via branch settings

    return payload


def setup_branch_protection(
    owner: str,
    repo: str,
    branch: str,
    config: BranchProtectionConfig,
    token: str,
    dry_run: bool = False,
) -> bool:
    """
    Configura proteção de branch via GitHub API.

    Returns:
        True se sucesso, False caso contrário
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}/protection"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    payload = build_protection_payload(config)

    if dry_run:
        console.print("\n[yellow]🔍 DRY RUN - Configuração que seria aplicada:[/yellow]")
        console.print(payload)
        return True

    # Aplicar proteção
    response = requests.put(url, headers=headers, json=payload)

    if response.status_code in (200, 201):
        console.print(f"[green]✅ Proteção aplicada em {branch}[/green]")

        # Aplicar required_signatures se necessário
        if config.required_signatures:
            sig_url = f"{url}/required_signatures"
            sig_response = requests.post(sig_url, headers=headers)
            if sig_response.status_code in (200, 201):
                console.print("[green]✅ Commits assinados habilitados[/green]")

        return True
    else:
        console.print("[red]❌ Erro ao aplicar proteção:[/red]")
        console.print(f"   Status: {response.status_code}")
        console.print(f"   Resposta: {response.text}")
        return False


def show_protection_summary(config: BranchProtectionConfig):
    """Exibe resumo da configuração de proteção."""
    table = Table(title=f"Configuração de Proteção - Nível: {config.level.upper()}")
    table.add_column("Configuração", style="cyan")
    table.add_column("Valor", style="green")

    table.add_row("Requer Pull Request", "✅" if config.require_pull_request else "❌")
    table.add_row("Aprovações necessárias", str(config.required_approving_review_count))
    table.add_row("Invalidar aprovações antigas", "✅" if config.dismiss_stale_reviews else "❌")
    table.add_row("Requer revisão de Code Owners", "✅" if config.require_code_owner_reviews else "❌")
    table.add_row("Requer aprovação do último push", "✅" if config.require_last_push_approval else "❌")
    table.add_row("Forçar para admins", "✅" if config.enforce_admins else "❌")
    table.add_row("Permitir force push", "✅" if config.allow_force_pushes else "❌")
    table.add_row("Permitir deletions", "✅" if config.allow_deletions else "❌")
    table.add_row("Requer resolução de conversas", "✅" if config.required_conversation_resolution else "❌")
    table.add_row("Commits assinados", "✅" if config.required_signatures else "❌")
    table.add_row("Histórico linear", "✅" if config.required_linear_history else "❌")

    if config.required_status_checks:
        checks = ", ".join(config.required_status_checks)
        table.add_row("Status checks", checks)

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="Setup GitHub Branch Protection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "repo",
        help="Repository no formato owner/repo",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Branch para proteger (padrão: main)",
    )
    parser.add_argument(
        "--level",
        choices=["minimum", "recommended", "maximum"],
        default="recommended",
        help="Nível de proteção (padrão: recommended)",
    )
    parser.add_argument(
        "--token",
        help="GitHub token (ou use GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas mostrar configuração sem aplicar",
    )

    args = parser.parse_args()

    # Validar formato do repo
    if "/" not in args.repo:
        console.print("[red]❌ Formato inválido. Use: owner/repo[/red]")
        return 1

    owner, repo = args.repo.split("/", 1)

    # Obter token
    token = args.token or os.getenv("GITHUB_TOKEN")
    if not token and not args.dry_run:
        console.print("[red]❌ GitHub token não fornecido[/red]")
        console.print("   Use --token ou defina GITHUB_TOKEN")
        return 1

    # Obter configuração
    config = PROTECTION_LEVELS[args.level]

    # Mostrar resumo
    console.print("\n[bold]Configurando proteção para:[/bold]")
    console.print(f"  Repository: {owner}/{repo}")
    console.print(f"  Branch: {args.branch}")
    console.print(f"  Nível: {args.level}")
    console.print()

    show_protection_summary(config)

    if not args.dry_run:
        console.print("\n[yellow]⚠️  Aplicando configuração...[/yellow]")
        success = setup_branch_protection(owner, repo, args.branch, config, token, args.dry_run)
        return 0 if success else 1
    else:
        console.print("\n[yellow]🔍 Dry run - nenhuma alteração foi feita[/yellow]")
        return 0


if __name__ == "__main__":
    sys.exit(main())
