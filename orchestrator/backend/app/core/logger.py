"""
Advanced colored, structured terminal logger for SourceGraph.

Provides ANSI-colored output with module-specific prefixes and
special "Handshake" formatting for Tailscale network events.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone, timedelta
from typing import ClassVar


# ── ANSI Color Codes ────────────────────────────────────────────
class _Colors:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"

    # Foreground
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    GRAY    = "\033[90m"

    # Backgrounds (for critical alerts)
    BG_RED  = "\033[41m"


# ── Module → Color mapping ─────────────────────────────────────
_MODULE_COLORS: dict[str, str] = {
    "INGEST":     _Colors.CYAN,
    "BUFFER":     _Colors.YELLOW,
    "SYNC":       _Colors.YELLOW,
    "SIMILARITY": _Colors.BLUE,
    "MATCH":      _Colors.GREEN,
    "GRAPH":      _Colors.MAGENTA,
    "GOLDEN":     _Colors.WHITE,
    "SIMULATE":   _Colors.MAGENTA,
    "ALERT":      _Colors.RED,
    "HANDSHAKE":  _Colors.MAGENTA,
    "STARTUP":    _Colors.GREEN,
    "SHUTDOWN":   _Colors.RED,
    "FEED":       _Colors.GRAY,
}

# IST timezone
_IST = timezone(timedelta(hours=5, minutes=30))


class ColoredFormatter(logging.Formatter):
    """Custom formatter that injects ANSI colors based on log level and module tag."""

    LEVEL_COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG:    _Colors.GRAY,
        logging.INFO:     _Colors.GREEN,
        logging.WARNING:  _Colors.YELLOW,
        logging.ERROR:    _Colors.RED,
        logging.CRITICAL: _Colors.BG_RED + _Colors.WHITE,
    }

    def format(self, record: logging.LogRecord) -> str:
        # Timestamp in IST
        now = datetime.now(_IST)
        ts = now.strftime("%H:%M:%S.%f")[:-3]

        # Level color
        level_color = self.LEVEL_COLORS.get(record.levelno, _Colors.WHITE)
        level_name = record.levelname.ljust(8)

        # Module tag (extracted from the first bracketed word in the message)
        module_tag = ""
        msg = record.getMessage()
        if msg.startswith("["):
            end = msg.find("]")
            if end != -1:
                tag = msg[1:end].upper()
                tag_color = _MODULE_COLORS.get(tag, _Colors.WHITE)
                module_tag = f"{tag_color}{_Colors.BOLD}[{tag}]{_Colors.RESET} "
                msg = msg[end + 1:].lstrip()

        return (
            f"{_Colors.DIM}{ts}{_Colors.RESET} "
            f"{level_color}{level_name}{_Colors.RESET} "
            f"{module_tag}"
            f"{msg}"
        )


def get_logger(name: str = "sourcegraph") -> logging.Logger:
    """Create or retrieve a colored logger instance."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

    return logger


def log_handshake(
    logger: logging.Logger,
    source_node: str,
    source_ip: str,
    target_node: str,
    target_ip: str,
) -> None:
    """Log a styled Tailscale network handshake event."""
    logger.info(
        f"[HANDSHAKE] 🤝 {_Colors.BOLD}{source_node}{_Colors.RESET} "
        f"{_Colors.DIM}({source_ip}){_Colors.RESET} "
        f"{_Colors.CYAN}→{_Colors.RESET} "
        f"{_Colors.BOLD}{target_node}{_Colors.RESET} "
        f"{_Colors.DIM}({target_ip}){_Colors.RESET}"
    )


def log_match_detected(
    logger: logging.Logger,
    golden_name: str,
    suspect_video: str,
    fused_score: float,
    verdict: str,
) -> None:
    """Log a styled piracy match detection."""
    pct = fused_score * 100
    verdict_color = (
        _Colors.RED if verdict == "PIRATE"
        else _Colors.YELLOW if verdict == "SUSPICIOUS"
        else _Colors.GREEN
    )

    logger.warning(
        f"[MATCH] 🚨 {_Colors.BOLD}{pct:.1f}% Match Detected{_Colors.RESET} — "
        f"Golden: {_Colors.CYAN}{golden_name}{_Colors.RESET} ↔ "
        f"Suspect: {_Colors.YELLOW}{suspect_video}{_Colors.RESET} — "
        f"Verdict: {verdict_color}{_Colors.BOLD}{verdict}{_Colors.RESET}"
    )


def log_ingest(
    logger: logging.Logger,
    video_name: str,
    has_visual: bool,
    has_text: bool,
    source_node: str | None = None,
) -> None:
    """Log a styled ingestion event."""
    visual_icon = "✅" if has_visual else "⬜"
    text_icon = "✅" if has_text else "⬜"
    node_str = f" from {_Colors.MAGENTA}{source_node}{_Colors.RESET}" if source_node else ""

    logger.info(
        f"[INGEST] 📥 {_Colors.BOLD}{video_name}{_Colors.RESET}{node_str} "
        f"| Visual {visual_icon} | Text {text_icon}"
    )
