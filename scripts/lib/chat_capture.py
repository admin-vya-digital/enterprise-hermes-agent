"""
Chat Capture Module - IMP-55

Captura conversas do GitHub Copilot em formato estruturado CHAT-*.md.

Author: @yves_marinho
Created: 2026-04-14
Version: 1.0.0
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """Representa uma mensagem na conversa"""

    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime
    message_id: str
    parent_id: Optional[str] = None
    tool_requests: List[Dict] = field(default_factory=list)
    reasoning_text: Optional[str] = None

    def to_markdown(self) -> str:
        """Converte mensagem para formato markdown"""
        time_str = self.timestamp.strftime("%H:%M:%S")
        role_upper = self.role.upper()

        md = f"## {time_str} — {role_upper}\n\n"

        if self.reasoning_text and len(self.reasoning_text) > 50:
            md += f"<details>\n<summary>Reasoning</summary>\n\n{self.reasoning_text}\n</details>\n\n"

        md += f"{self.content}\n"

        if self.tool_requests:
            md += "\n**Tools used:**\n"
            for tool in self.tool_requests:
                tool_name = tool.get("name", "unknown")
                md += f"- `{tool_name}`\n"

        md += "\n---\n\n"
        return md


@dataclass
class ChatMetadata:
    """Metadata da conversa"""

    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    participants: List[Dict] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    related_sessions: List[str] = field(default_factory=list)
    related_specs: List[str] = field(default_factory=list)
    template_version: str = "1.0.0"

    @property
    def duration_seconds(self) -> int:
        """Duração da conversa em segundos"""
        if not self.end_time:
            return 0
        return int((self.end_time - self.start_time).total_seconds())

    @property
    def duration_formatted(self) -> str:
        """Duração formatada (HH:MM:SS)"""
        seconds = self.duration_seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}min {secs}s"
        elif minutes > 0:
            return f"{minutes}min {secs}s"
        else:
            return f"{secs}s"

    def to_yaml_frontmatter(self) -> str:
        """Converte metadata para YAML frontmatter"""
        data = {
            "type": "chat",
            "session_date": self.start_time.strftime("%Y-%m-%d"),
            "session_id": self.session_id,
            "start_time": self.start_time.strftime("%H:%M:%S"),
            "end_time": self.end_time.strftime("%H:%M:%S") if self.end_time else None,
            "participants": self.participants,
            "topics": self.topics,
            "related_sessions": self.related_sessions,
            "related_specs": self.related_specs,
            "template_version": self.template_version,
        }

        return "---\n" + yaml.dump(data, allow_unicode=True, sort_keys=False) + "---\n"


class ChatCapture:
    """Captura conversas do GitHub Copilot"""

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root)
        self.sessions_dir = self.workspace_root / "docs" / "SESSIONS"

        # Detectar workspace storage path
        self.workspace_storage = self._detect_workspace_storage()
        self.transcripts_dir = (
            self.workspace_storage / "GitHub.copilot-chat" / "transcripts"
            if self.workspace_storage
            else None
        )

    def _detect_workspace_storage(self) -> Optional[Path]:
        """
        Detecta o diretório workspace storage do VS Code.

        Path esperado:
        ~/.config/Code - Insiders/User/workspaceStorage/{workspace-id}/
        """
        vscode_config = Path.home() / ".config" / "Code - Insiders" / "User" / "workspaceStorage"

        if not vscode_config.exists():
            log.warning("VS Code workspace storage não encontrado: %s", vscode_config)
            return None

        # Procurar pelo workspace mais recente com GitHub.copilot-chat
        workspaces = []
        for ws_dir in vscode_config.iterdir():
            if not ws_dir.is_dir():
                continue

            copilot_dir = ws_dir / "GitHub.copilot-chat"
            if copilot_dir.exists():
                # Usar timestamp do diretório para encontrar o mais recente
                workspaces.append((ws_dir.stat().st_mtime, ws_dir))

        if not workspaces:
            log.warning("Nenhum workspace com GitHub.copilot-chat encontrado")
            return None

        # Retornar o mais recente
        workspaces.sort(reverse=True)
        workspace_path = workspaces[0][1]
        log.info("Workspace storage detectado: %s", workspace_path)
        return workspace_path

    def list_transcripts(self) -> List[Path]:
        """Lista todos os transcripts disponíveis"""
        if not self.transcripts_dir or not self.transcripts_dir.exists():
            log.warning("Transcripts directory não encontrado")
            return []

        transcripts = sorted(
            self.transcripts_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        log.info("Encontrados %d transcripts", len(transcripts))
        return transcripts

    def get_latest_transcript(self) -> Optional[Path]:
        """Retorna o transcript mais recente"""
        transcripts = self.list_transcripts()
        return transcripts[0] if transcripts else None

    def parse_transcript(self, transcript_path: Path) -> tuple[ChatMetadata, List[ChatMessage]]:
        """
        Parse transcript JSONL → ChatMetadata + ChatMessage[]

        Estrutura JSONL:
        - type: "session.start" | "user.message" | "assistant.message" | "tool.result"
        - data: { ... }
        - id: message ID
        - timestamp: ISO 8601
        - parentId: parent message ID
        """
        messages = []
        metadata = None
        session_id = None
        start_time = None
        end_time = None

        log.info("Parsing transcript: %s", transcript_path)

        with open(transcript_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    entry = json.loads(line.strip())
                except json.JSONDecodeError as e:
                    log.error("JSON decode error at line %d: %s", line_num, e)
                    continue

                entry_type = entry.get("type", "")
                timestamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))

                # Session start
                if entry_type == "session.start":
                    session_id = entry["data"]["sessionId"]
                    start_time = timestamp
                    log.debug("Session start: %s at %s", session_id, start_time)

                # User message
                elif entry_type == "user.message":
                    content = entry["data"].get("content", "")
                    message_id = entry["id"]
                    parent_id = entry.get("parentId")

                    msg = ChatMessage(
                        role="user",
                        content=content,
                        timestamp=timestamp,
                        message_id=message_id,
                        parent_id=parent_id,
                    )
                    messages.append(msg)
                    log.debug("User message: %s chars", len(content))

                # Assistant message
                elif entry_type == "assistant.message":
                    content = entry["data"].get("content", "")
                    message_id = entry["id"]
                    parent_id = entry.get("parentId")
                    tool_requests = entry["data"].get("toolRequests", [])
                    reasoning_text = entry["data"].get("reasoningText")

                    msg = ChatMessage(
                        role="assistant",
                        content=content,
                        timestamp=timestamp,
                        message_id=message_id,
                        parent_id=parent_id,
                        tool_requests=tool_requests,
                        reasoning_text=reasoning_text,
                    )
                    messages.append(msg)
                    log.debug("Assistant message: %s chars, %d tools", len(content), len(tool_requests))

                # Update end_time for every entry
                end_time = timestamp

        # Create metadata
        if not session_id or not start_time:
            raise ValueError(f"Invalid transcript: missing session_id or start_time in {transcript_path}")

        metadata = ChatMetadata(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            participants=[
                {"user": "yves_marinho"},
                {"agent": "github-copilot"},
            ],
        )

        log.info("Parsed %d messages (duration: %s)", len(messages), metadata.duration_formatted)
        return metadata, messages

    def extract_topics(self, messages: List[ChatMessage]) -> List[str]:
        """
        Extrai topics da conversa usando keyword extraction simples.

        Estratégia:
        1. Identificar IMP-XXX mentions
        2. Identificar nomes de arquivos/diretórios mencionados
        3. Identificar palavras-chave técnicas (database, search, validation, etc.)
        """
        topics = set()

        # Patterns para detecção
        imp_pattern = r"IMP-\d+"
        file_pattern = r"[a-zA-Z_\-]+\.(py|md|yaml|sh|json)"

        import re

        all_content = " ".join(msg.content for msg in messages)

        # IMP-XXX
        imp_matches = re.findall(imp_pattern, all_content, re.IGNORECASE)
        topics.update(imp_matches)

        # Arquivos mencionados (limitar a 5)
        file_matches = re.findall(file_pattern, all_content)
        topics.update(file_matches[:5])

        # Keywords técnicas (simplificado - pode melhorar com TF-IDF)
        keywords = [
            "database", "search", "validation", "testing", "implementation",
            "spec", "plan", "tasks", "session", "chat", "capture",
            "docker", "git", "python", "makefile", "ansible",
        ]
        for keyword in keywords:
            if keyword.lower() in all_content.lower():
                topics.add(keyword)

        log.info("Extracted %d topics", len(topics))
        return sorted(topics)[:10]  # Limitar a 10 topics

    def capture_to_markdown(
        self,
        transcript_path: Path,
        session_date: Optional[str] = None,
    ) -> Path:
        """
        Captura transcript e salva em CHAT-YYYY-MM-DD-HHmm.md

        Args:
            transcript_path: Path para transcript JSONL
            session_date: Data da sessão (YYYY-MM-DD), default = hoje

        Returns:
            Path para arquivo CHAT-*.md criado
        """
        # Parse transcript
        metadata, messages = self.parse_transcript(transcript_path)

        # Extract topics
        metadata.topics = self.extract_topics(messages)

        # Determine session date
        if not session_date:
            session_date = metadata.start_time.strftime("%Y-%m-%d")

        # Create session directory
        session_dir = self.sessions_dir / session_date
        session_dir.mkdir(parents=True, exist_ok=True)

        # Generate chat filename
        time_str = metadata.start_time.strftime("%H%M")
        chat_filename = f"CHAT-{session_date}-{time_str}.md"
        chat_path = session_dir / chat_filename

        # Generate markdown content
        md_content = self._generate_markdown(metadata, messages)

        # Write file
        with open(chat_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        log.info("✅ Chat captured: %s (%d messages, %s)",
                 chat_path, len(messages), metadata.duration_formatted)

        return chat_path

    def _generate_markdown(self, metadata: ChatMetadata, messages: List[ChatMessage]) -> str:
        """Gera conteúdo markdown completo"""
        md = metadata.to_yaml_frontmatter()
        md += "\n"

        # Title
        date_str = metadata.start_time.strftime("%Y-%m-%d %H:%M")
        topics_str = ", ".join(metadata.topics[:3]) if metadata.topics else "General Discussion"
        md += f"# CHAT — {date_str} — {topics_str}\n\n"

        # Metadata summary
        md += f"**Session ID**: {metadata.session_id}  \n"
        md += f"**Duration**: {metadata.duration_formatted}  \n"
        md += f"**Topics**: {', '.join(metadata.topics)}  \n"
        md += "\n---\n\n"

        # Messages
        for msg in messages:
            md += msg.to_markdown()

        # Summary (placeholder - pode ser preenchido manualmente ou via LLM)
        md += "\n## Summary\n\n"
        md += "**Topics covered**:\n"
        for topic in metadata.topics:
            md += f"- {topic}\n"
        md += "\n"
        md += "**Decisions made**:\n"
        md += "- (To be filled)\n\n"
        md += "**Next steps**:\n"
        md += "- (To be filled)\n"

        return md


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Capture GitHub Copilot conversations")
    parser.add_argument("--workspace", type=Path, default=Path.cwd(), help="Workspace root")
    parser.add_argument("--latest", action="store_true", help="Capture latest transcript")
    parser.add_argument("--transcript", type=Path, help="Specific transcript to capture")
    parser.add_argument("--session-date", help="Session date (YYYY-MM-DD)")

    args = parser.parse_args()

    capture = ChatCapture(args.workspace)

    if args.latest:
        transcript_path = capture.get_latest_transcript()
        if not transcript_path:
            log.error("No transcripts found")
            return 1
    elif args.transcript:
        transcript_path = args.transcript
    else:
        log.error("Specify --latest or --transcript")
        return 1

    try:
        chat_path = capture.capture_to_markdown(transcript_path, args.session_date)
        print(f"✅ Chat captured: {chat_path}")
        return 0
    except Exception as e:
        log.error("Capture failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
