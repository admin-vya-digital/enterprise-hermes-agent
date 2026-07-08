#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31.0",
# ]
# ///
"""
-------------------------------------------------------------------------
NOME..: update_hermes_agent_version.py
LANG..: Python3
TITULO: Verifica a última release de produção do hermes-agent no GitHub e
        atualiza HERMES_AGENT_REF/HERMES_AGENT_SHA no Dockerfile
DATA..: 08/07/2026 10:40
MODIFICADO: 08/07/2026 10:40
VERSÃO: 0.1.0
HOST..: local / CI
LOCAL.: scripts/update_hermes_agent_version.py
OBS...: usa a API pública do GitHub (sem credenciais) para o repositório
        upstream NousResearch/hermes-agent; opcionalmente lê um token em
        .secrets/github.json para evitar rate limit de requisições anônimas

DEPEND: requests

-------------------------------------------------------------------------
Modifications.....:
 Date          Rev    Author           Description
 08/07/2026    1      Claude Code      Elaboração

-------------------------------------------------------------------------
STATUS: DEV

Uso:
  python scripts/update_hermes_agent_version.py
  python scripts/update_hermes_agent_version.py --dry-run
  python scripts/update_hermes_agent_version.py --dockerfile caminho/Dockerfile
"""

import argparse
import logging
import re
import sys
from pathlib import Path

import requests

UPSTREAM_REPO = "NousResearch/hermes-agent"
GITHUB_API = "https://api.github.com"
DEFAULT_DOCKERFILE = Path("src/hermes_agent/Dockerfile")


def config_logging() -> bool:
    """
    Configura logging estruturado do programa.

    :return: True após configuração concluída.
    :rtype: bool
    """
    logger = logging.getLogger()
    if logger.hasHandlers():
        return True
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        handlers=[logging.StreamHandler()],
    )
    logging.info("=== Programa: %s ===", Path(sys.argv[0]).name)
    return True


def _load_github_token() -> str | None:
    """
    Carrega token do GitHub em .secrets/github.json, se existir.

    :return: Token ou None se o arquivo não existir/for inválido.
    :rtype: str | None
    """
    try:
        path = Path(".secrets") / "github.json"
        if not path.exists():
            return None
        import json

        creds = json.loads(path.read_text(encoding="utf-8"))
        return creds.get("token")
    except Exception as errorMsg:
        logging.warning("Não foi possível ler .secrets/github.json: %s", errorMsg)
        return None


def _github_headers() -> dict:
    """
    Monta headers padrão para chamadas à API do GitHub.

    :return: Dicionário de headers HTTP.
    :rtype: dict
    """
    headers = {"Accept": "application/vnd.github+json"}
    token = _load_github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_latest_release(repo: str) -> dict | bool:
    """
    Busca a última release publicada (produção) de um repositório GitHub.

    :param repo: Repositório no formato "owner/repo".
    :type repo: str
    :return: Dicionário com tag_name e demais campos da release, ou False em erro.
    :rtype: dict | bool

    >>> isinstance(fetch_latest_release(""), bool)
    True
    """
    logging.info("=== Função: %s ===", sys._getframe().f_code.co_name)
    if not repo or not isinstance(repo, str):
        logging.error("Parâmetro 'repo' inválido")
        return False
    try:
        url = f"{GITHUB_API}/repos/{repo}/releases/latest"
        response = requests.get(url, headers=_github_headers(), timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as errorMsg:
        logging.error("Erro ao buscar última release de %s", repo)
        logging.error("Exception occurred", exc_info=True)
        logging.error(errorMsg)
        return False


def resolve_commit_sha(repo: str, tag: str) -> str | bool:
    """
    Resolve o SHA de commit imutável correspondente a uma tag (lida ou anotada).

    :param repo: Repositório no formato "owner/repo".
    :type repo: str
    :param tag: Nome da tag (ex: "v2026.7.7.2").
    :type tag: str
    :return: SHA de 40 caracteres do commit, ou False em erro.
    :rtype: str | bool
    """
    logging.info("=== Função: %s ===", sys._getframe().f_code.co_name)
    if not repo or not isinstance(repo, str):
        logging.error("Parâmetro 'repo' inválido")
        return False
    if not tag or not isinstance(tag, str):
        logging.error("Parâmetro 'tag' inválido")
        return False
    try:
        headers = _github_headers()
        ref_url = f"{GITHUB_API}/repos/{repo}/git/ref/tags/{tag}"
        ref_resp = requests.get(ref_url, headers=headers, timeout=30)
        ref_resp.raise_for_status()
        ref_obj = ref_resp.json()["object"]

        if ref_obj["type"] == "commit":
            return ref_obj["sha"]

        # Tag anotada: o objeto referenciado é um "tag object", não o commit.
        # Precisa de uma segunda chamada para chegar no commit de fato.
        tag_url = f"{GITHUB_API}/repos/{repo}/git/tags/{ref_obj['sha']}"
        tag_resp = requests.get(tag_url, headers=headers, timeout=30)
        tag_resp.raise_for_status()
        return tag_resp.json()["object"]["sha"]
    except Exception as errorMsg:
        logging.error("Erro ao resolver SHA da tag %s em %s", tag, repo)
        logging.error("Exception occurred", exc_info=True)
        logging.error(errorMsg)
        return False


def update_dockerfile(dockerfile_path: Path, ref: str, sha: str, dry_run: bool) -> bool:
    """
    Atualiza HERMES_AGENT_REF e HERMES_AGENT_SHA no Dockerfile informado.

    :param dockerfile_path: Caminho do Dockerfile a atualizar.
    :type dockerfile_path: Path
    :param ref: Nova tag de release (ex: "v2026.7.7.2").
    :type ref: str
    :param sha: Novo SHA de commit imutável correspondente à tag.
    :type sha: str
    :param dry_run: Se True, apenas mostra o diff sem gravar o arquivo.
    :type dry_run: bool
    :return: True se atualizado (ou dry-run concluído) com sucesso, False em erro.
    :rtype: bool
    """
    logging.info("=== Função: %s ===", sys._getframe().f_code.co_name)
    if not dockerfile_path.exists():
        logging.error("Dockerfile não encontrado: %s", dockerfile_path)
        return False
    if not ref or not sha:
        logging.error("Parâmetros 'ref'/'sha' inválidos")
        return False
    try:
        content = dockerfile_path.read_text(encoding="utf-8")

        new_content, ref_matches = re.subn(
            r"^ARG HERMES_AGENT_REF=.*$",
            f"ARG HERMES_AGENT_REF={ref}",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        new_content, sha_matches = re.subn(
            r"^ARG HERMES_AGENT_SHA=.*$",
            f"ARG HERMES_AGENT_SHA={sha}",
            new_content,
            count=1,
            flags=re.MULTILINE,
        )

        if not ref_matches or not sha_matches:
            logging.error(
                "Linha ARG HERMES_AGENT_REF= ou ARG HERMES_AGENT_SHA= não encontrada em %s",
                dockerfile_path,
            )
            return False

        if new_content == content:
            logging.info(
                "%s já está na última versão (%s / %s) — nada a fazer",
                dockerfile_path,
                ref,
                sha,
            )
            return True

        if dry_run:
            logging.info("[dry-run] HERMES_AGENT_REF -> %s", ref)
            logging.info("[dry-run] HERMES_AGENT_SHA -> %s", sha)
            return True

        dockerfile_path.write_text(new_content, encoding="utf-8")
        logging.info("Dockerfile atualizado: %s", dockerfile_path)
        return True
    except Exception as errorMsg:
        logging.error("Erro ao atualizar %s", dockerfile_path)
        logging.error("Exception occurred", exc_info=True)
        logging.error(errorMsg)
        return False


def main() -> int:
    """
    Ponto de entrada do script.

    :return: Código de saída do processo (0 = sucesso).
    :rtype: int
    """
    config_logging()
    logging.info("=== Função: %s ===", sys._getframe().f_code.co_name)

    parser = argparse.ArgumentParser(
        description="Atualiza HERMES_AGENT_REF/HERMES_AGENT_SHA no Dockerfile "
        "conforme a última release publicada de NousResearch/hermes-agent."
    )
    parser.add_argument(
        "--dockerfile",
        type=Path,
        default=DEFAULT_DOCKERFILE,
        help=f"Caminho do Dockerfile (padrão: {DEFAULT_DOCKERFILE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas mostra o que seria alterado, sem gravar o arquivo",
    )
    args = parser.parse_args()

    release = fetch_latest_release(UPSTREAM_REPO)
    if not isinstance(release, dict):
        logging.error("Não foi possível obter a última release de %s", UPSTREAM_REPO)
        return 1

    tag = release.get("tag_name")
    if not tag:
        logging.error("Release retornada sem 'tag_name'")
        return 1
    logging.info("==> VAR: tag TYPE: %s, CONTENT: %s", type(tag), tag)

    sha = resolve_commit_sha(UPSTREAM_REPO, tag)
    if not isinstance(sha, str):
        logging.error("Não foi possível resolver o commit SHA da tag %s", tag)
        return 1
    logging.info("==> VAR: sha TYPE: %s, CONTENT: %s", type(sha), sha)

    ok = update_dockerfile(args.dockerfile, tag, sha, args.dry_run)

    logging.info("=== Termino Função: %s ===", sys._getframe().f_code.co_name)
    logging.info("=== Termino programa: %s ===", Path(sys.argv[0]).name)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
