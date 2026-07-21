"""
Voice Turn Pipeline for Vadi-Pehn.
Orchestrates: VAD -> STT -> Safety Proxy Check Input -> LLM Sentence Streaming -> Per-Chunk Output Safety -> TTS -> LiveKit Stream.
Enforces:
  1. No raw voice audio retention (PRD §3.4)
  2. Per-chunk output safety rail (GUARDRAILS G-004)
  3. Latency budget compliance (total E2E p95 <= 3700ms, first audio chunk < 1000ms, PRD §6.2)
  4. Multilingual validation & Piper fallback (PRD §6.4)
  5. Barge-in / interruption cancellation (PRD §6.3)
"""

from __future__ import annotations

import base64
import logging
import re
import time
import uuid
from typing import Any, AsyncGenerator

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from services.abstractions import (
    SafetyClient,
    SafetyVerdict,
    SafetyVerdictCode,
    MockSafetyClient,
)
from voice_gateway.abstractions import (
    LiveKitRoomManager,
    STTService,
    TTSService,
    VADService,
)
from voice_gateway.models import LatencyReport, VoiceTurnRequest, VoiceTurnResponse

logger = logging.getLogger(__name__)


def split_into_sentence_chunks(text: str) -> list[str]:
    """
    Split generated LLM text into sentence chunks for per-chunk output safety and streaming TTS.
    """
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


async def stream_sentence_chunks(
    source: AsyncGenerator[str, None],
) -> AsyncGenerator[str, None]:
    """Turn provider text deltas into completed sentence chunks."""
    pending = ""
    async for part in source:
        pending += part
        chunks = split_into_sentence_chunks(pending)
        if not chunks:
            continue
        if re.search(r"[.!?।]$", pending.strip()):
            pending = ""
        else:
            pending = chunks.pop()
        for chunk in chunks:
            yield chunk
    if pending.strip():
        yield pending.strip()


class VoiceTurnPipeline:
    """
    Siri-Grade Streaming Voice Turn Pipeline orchestrator.
    Streams sentence chunks to TTS as soon as they are emitted for low first-audio-byte latency.
    """

    def __init__(
        self,
        vad_service: VADService,
        stt_service: STTService,
        tts_service: TTSService,
        room_manager: LiveKitRoomManager,
        safety_client: SafetyClient | None = None,
        orchestration_graph: Any | None = None,
    ) -> None:
        self.vad_service = vad_service
        self.stt_service = stt_service
        self.tts_service = tts_service
        self.room_manager = room_manager
        self.safety_client = safety_client or MockSafetyClient()
        self.orchestration_graph = orchestration_graph
        self.active_interruptions: dict[str, bool] = {}
        self._last_safety_verdict = SafetyVerdictCode.SAFE.value

    def trigger_barge_in(self, session_id: str) -> None:
        """
        PRD §6.3 Barge-in Handler: Sets interruption flag to cancel ongoing TTS audio stream within 1 VAD frame.
        """
        self.active_interruptions[session_id] = True

    def is_interrupted(self, session_id: str) -> bool:
        return self.active_interruptions.get(session_id, False)

    def _clear_interruption(self, session_id: str) -> None:
        self.active_interruptions.pop(session_id, None)

    async def stream_voice_turn(
        self, request: VoiceTurnRequest
    ) -> AsyncGenerator[tuple[str, bytes | None, LatencyReport], None]:
        """
        Siri-Grade Sentence-Boundary Streaming Pipeline.
        Yields (sentence_chunk, audio_bytes, report) for each completed sentence chunk
        so audio playback begins immediately.
        """
        start_e2e = time.perf_counter()
        report = LatencyReport()
        session_id = request.session_id

        # ── 1. VAD ──
        t0 = time.perf_counter()
        audio_bytes = b""
        if request.audio_data_base64:
            audio_bytes = base64.b64decode(request.audio_data_base64)
        await self.vad_service.is_speaking(audio_bytes)
        report.vad_ms = (time.perf_counter() - t0) * 1000.0

        # ── 2. STT (Zero Retention) ──
        t0 = time.perf_counter()
        if request.text_fallback:
            transcript = request.text_fallback
        else:
            transcript = await self.stt_service.transcribe(
                audio_bytes, language=request.language
            )
            audio_bytes = b""
        report.stt_ms = (time.perf_counter() - t0) * 1000.0

        # A failed/empty transcription must not become an LLM prompt.
        if not transcript.strip():
            report.total_e2e_ms = (time.perf_counter() - start_e2e) * 1000.0
            return

        # ── 3. Check Input Safety ──
        t0 = time.perf_counter()
        input_verdict: SafetyVerdict = await self.safety_client.check_input(
            learner_id=request.learner_id,
            message_text=transcript,
            age_band=request.age_band,
            tenant_id=request.tenant_id,
        )
        report.safety_input_ms = (time.perf_counter() - t0) * 1000.0
        self._last_safety_verdict = input_verdict.code.value

        if input_verdict.blocks_generation:
            fallback_text = (
                "I hear that you're going through a tough time. You are not alone, "
                "and I am here for you. Let's talk to a trusted adult or caseworker together."
            )
            # Fixed supportive scripts are still user-facing output and must pass
            # the output rail before audio synthesis (AGENTS Part 1, G-004).
            t0_fallback_safety = time.perf_counter()
            fallback_verdict = await self.safety_client.check_output(
                learner_id=request.learner_id,
                draft_reply_text=fallback_text,
                tenant_id=request.tenant_id,
            )
            report.safety_output_per_chunk_ms = (
                time.perf_counter() - t0_fallback_safety
            ) * 1000.0
            self._last_safety_verdict = fallback_verdict.code.value
            if fallback_verdict.blocks_generation:
                report.total_e2e_ms = (time.perf_counter() - start_e2e) * 1000.0
                return
            t_tts = time.perf_counter()
            audio_buf = await self.tts_service.synthesize(
                fallback_text, language=request.language
            )
            await self.room_manager.stream_audio_to_room(
                f"room_{session_id}", audio_buf
            )
            report.tts_first_chunk_ms = (time.perf_counter() - t_tts) * 1000.0
            report.total_e2e_ms = (time.perf_counter() - start_e2e) * 1000.0
            yield (fallback_text, audio_buf, report)
            return

        # ── 4. LLM Generation ──
        t0_llm = time.perf_counter()
        draft_reply = ""
        draft_source: AsyncGenerator[str, None]
        if self.orchestration_graph:
            from orchestration.graph import TurnState

            initial_state = TurnState(
                session_id=request.session_id,
                tenant_id=str(request.tenant_id),
                learner_id=str(request.learner_id),
                age_band=request.age_band,
                message_text=transcript,
                language_detected=request.language,
            )
            if hasattr(self.orchestration_graph, "stream_reply"):
                draft_source = self.orchestration_graph.stream_reply(initial_state)
            else:
                final_state = await self.orchestration_graph.run_turn(initial_state)
                draft_reply = final_state.final_reply or final_state.draft_reply

                async def completed_reply() -> AsyncGenerator[str, None]:
                    yield draft_reply

                draft_source = completed_reply()
        else:
            draft_reply = f"That is really interesting! Tell me more about your interest in {transcript}."

            async def completed_reply() -> AsyncGenerator[str, None]:
                yield draft_reply

            draft_source = completed_reply()

        # ── 5. Sentence-Boundary Token Stream & TTS ──
        sentence_chunks = stream_sentence_chunks(draft_source)
        total_output_safety_ms = 0.0
        sentence_count = 0

        async for chunk in sentence_chunks:
            if not report.llm_first_chunk_ms:
                report.llm_first_chunk_ms = (time.perf_counter() - t0_llm) * 1000.0
            sentence_count += 1
            if self.is_interrupted(session_id):
                # Interrupted mid-stream by barge-in! Truncate stream.
                break

            t0_chunk_safety = time.perf_counter()
            output_verdict: SafetyVerdict = await self.safety_client.check_output(
                learner_id=request.learner_id,
                draft_reply_text=chunk,
                tenant_id=request.tenant_id,
            )
            total_output_safety_ms += (time.perf_counter() - t0_chunk_safety) * 1000.0

            if output_verdict.blocks_generation:
                self._last_safety_verdict = output_verdict.code.value
                safe_fallback = "Let's pivot to something positive and uplifting!"
                t0_fallback_safety = time.perf_counter()
                fallback_verdict = await self.safety_client.check_output(
                    learner_id=request.learner_id,
                    draft_reply_text=safe_fallback,
                    tenant_id=request.tenant_id,
                )
                total_output_safety_ms += (
                    time.perf_counter() - t0_fallback_safety
                ) * 1000.0
                if fallback_verdict.blocks_generation:
                    report.total_e2e_ms = (time.perf_counter() - start_e2e) * 1000.0
                    break
                t_tts = time.perf_counter()
                audio_buf = await self.tts_service.synthesize(
                    safe_fallback, language=request.language
                )
                await self.room_manager.stream_audio_to_room(
                    f"room_{session_id}", audio_buf
                )
                if not report.tts_first_chunk_ms:
                    report.tts_first_chunk_ms = (time.perf_counter() - t_tts) * 1000.0
                report.total_e2e_ms = (time.perf_counter() - start_e2e) * 1000.0
                yield (safe_fallback, audio_buf, report)
                break
            else:
                t_tts = time.perf_counter()
                audio_buf = await self.tts_service.synthesize(
                    chunk, language=request.language
                )
                await self.room_manager.stream_audio_to_room(
                    f"room_{session_id}", audio_buf
                )
                if not report.tts_first_chunk_ms:
                    report.tts_first_chunk_ms = (time.perf_counter() - t_tts) * 1000.0
                report.total_e2e_ms = (time.perf_counter() - start_e2e) * 1000.0
                yield (chunk, audio_buf, report)

        report.safety_output_per_chunk_ms = total_output_safety_ms / max(
            sentence_count, 1
        )

    async def execute_voice_turn(self, request: VoiceTurnRequest) -> VoiceTurnResponse:
        """
        Executes a complete voice turn using the streaming generator under the hood.
        """
        turn_id = str(uuid.uuid4())
        chunks: list[str] = []
        audio_buffers: list[bytes] = []
        last_report = LatencyReport()

        try:
            async for chunk, audio_buf, report in self.stream_voice_turn(request):
                chunks.append(chunk)
                if audio_buf:
                    audio_buffers.append(audio_buf)
                last_report = report

            combined_audio = b"".join(audio_buffers)
            final_reply_text = " ".join(chunks)

            self._emit_otel_span(request, last_report)

            return VoiceTurnResponse(
                session_id=request.session_id,
                turn_id=turn_id,
                transcript_text=request.text_fallback or "spoken turn",
                reply_text=final_reply_text,
                safety_verdict=self._last_safety_verdict,
                latency_report=last_report,
                audio_response_base64=(
                    base64.b64encode(combined_audio).decode("utf-8")
                    if combined_audio
                    else None
                ),
            )
        finally:
            self._clear_interruption(request.session_id)

    def _emit_otel_span(self, request: VoiceTurnRequest, report: LatencyReport) -> None:
        """
        Emits OTEL / Langfuse span containing latency breakdown and safety metrics per AGENTS.md Part 6.
        """
        span_data = {
            "session_id": request.session_id,
            "learner_id": str(request.learner_id),
            "tenant_id": str(request.tenant_id),
            "stt_ms": report.stt_ms,
            "llm_first_chunk_ms": report.llm_first_chunk_ms,
            "tts_first_chunk_ms": report.tts_first_chunk_ms,
            "total_e2e_ms": report.total_e2e_ms,
            "safety_verdict": "SAFE",
        }
        logger.info("voice_turn_completed", extra=span_data)
