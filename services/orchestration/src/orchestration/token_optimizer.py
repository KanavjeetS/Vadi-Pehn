"""
Tokenization & Context Compression Optimizer for Vadi-Pehn.
Optimizes LLM context usage, calculates approximate token budgets, and prunes older turns
while maintaining safety instructions and core memory facts.
"""

from __future__ import annotations

import re
from typing import Any


class TokenOptimizer:
    """
    Token budget manager and prompt compressor.
    Enforces maximum token caps (e.g. 2048 tokens context window) for fast local LLM inference.
    """

    def __init__(self, max_context_tokens: int = 2048, chars_per_token: float = 4.0) -> None:
        self.max_context_tokens = max_context_tokens
        self.chars_per_token = chars_per_token

    def estimate_tokens(self, text: str) -> int:
        """Rough estimation of token count from character count."""
        if not text:
            return 0
        return int(len(text) / self.chars_per_token)

    def estimate_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        """Calculate total estimated tokens across all messages in history."""
        total = 0
        for msg in messages:
            total += self.estimate_tokens(msg.get("content", "")) + 4
        return total

    def compress_history(
        self,
        messages: list[dict[str, str]],
        max_budget: int | None = None,
    ) -> list[dict[str, str]]:
        """
        Compresses dialogue history by retaining the system prompt (first message)
        and sliding window of recent conversation turns to fit under max_budget.
        """
        budget = max_budget or self.max_context_tokens
        if not messages:
            return []

        system_msg = messages[0] if messages[0].get("role") == "system" else None
        chat_msgs = messages[1:] if system_msg else messages[:]

        current_tokens = self.estimate_messages_tokens(messages)
        if current_tokens <= budget:
            return messages

        # Slide from newest to oldest
        retained: list[dict[str, str]] = []
        accumulated_tokens = self.estimate_tokens(system_msg.get("content", "")) if system_msg else 0

        for msg in reversed(chat_msgs):
            msg_tokens = self.estimate_tokens(msg.get("content", "")) + 4
            if accumulated_tokens + msg_tokens <= budget:
                retained.insert(0, msg)
                accumulated_tokens += msg_tokens
            else:
                break

        final_history: list[dict[str, str]] = []
        if system_msg:
            final_history.append(system_msg)
        final_history.extend(retained)

        return final_history

    def sanitize_and_deduplicate_retrieved_context(
        self, chunks: list[str], max_chunk_tokens: int = 512
    ) -> str:
        """
        Deduplicates retrieved memory chunks and formats them cleanly for prompt inclusion.
        """
        seen: set[str] = set()
        unique_chunks: list[str] = []
        token_count = 0

        for chunk in chunks:
            cleaned = re.sub(r"\s+", " ", chunk).strip()
            if cleaned not in seen:
                seen.add(cleaned)
                c_tokens = self.estimate_tokens(cleaned)
                if token_count + c_tokens <= max_chunk_tokens:
                    unique_chunks.append(f"- {cleaned}")
                    token_count += c_tokens
                else:
                    break

        return "\n".join(unique_chunks)
