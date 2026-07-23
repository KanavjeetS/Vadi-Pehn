# Adversarial Challenge Report: Milestone 3 (Requirement R3 — Child Portal & Voice Synthesis)

**Verdict**: **FAIL** (Backend test suite and TTS fallback chain pass 100%, but 3 critical/medium frontend edge-case bugs were uncovered in `child.js` affecting user gesture handling, audio feedback loops, and UI timer state corruption).

---

## 1. Observation

### 1.1 Test Execution Results
- Command executed: `py -m pytest services/voice-gateway/tests/`
- Result: **15 passed in 1.54s**
  - `services\voice-gateway\tests\test_pipeline.py`: 11 passed
  - `services\voice-gateway\tests\test_providers.py`: 4 passed
- Command executed: `py -m pytest .agents/challenger_m3_1/test_fallback_empirical.py`
- Result: **5 passed in 0.94s** (Empirical TTS fallback chain tests)

### 1.2 Voice Fallback Chain Code Inspection
- File `services/voice-gateway/src/voice_gateway/providers.py` (lines 76–110):
  ```python
  class ElevenLabsTTSService(TTSService):
      def __init__(self, fallback_tts: TTSService | None = None) -> None:
          self.fallback_tts = fallback_tts

      async def synthesize(self, text: str, language: str = "en") -> bytes:
          if not settings.elevenlabs.api_key:
              if self.fallback_tts:
                  return await self.fallback_tts.synthesize(text, language)
              raise RuntimeError("No TTS provider is configured")

          try:
              ...
          except Exception as exc:
              logger.warning("ElevenLabs TTS call failed, using fallback: %s", exc)
              if self.fallback_tts:
                  return await self.fallback_tts.synthesize(text, language)
              raise RuntimeError("TTS provider unavailable") from exc
  ```
- File `services/voice-gateway/src/voice_gateway/tts.py` (lines 81–123):
  ```python
  class KokoroTTSService(TTSService):
      def __init__(self, kokoro_url: str | None = None, fallback_service: PiperTTSService | None = None) -> None:
          ...
      async def synthesize(self, text: str, language: str = "en") -> bytes:
          if language == "pa":
              return await self.fallback_service.synthesize(text, language)
          try:
              ...
          except Exception:
              return await self.fallback_service.synthesize(text, language)
  ```
- File `services/voice-gateway/src/voice_gateway/tts.py` (lines 45–79):
  ```python
  class PiperTTSService(TTSService):
      ...
      async def synthesize(self, text: str, language: str = "pa") -> bytes:
          try:
              cmd = [self.piper_path, "--model", self.model_path, "--output-raw"]
              process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
              stdout, stderr = process.communicate(input=text.encode("utf-8"), timeout=3.0)
              ...
          except Exception:
              return b"ERR_PIPER_TTS_FAILED"
  ```

### 1.3 Web Audio API & Canvas Visualizer Code Inspection (`child.js`)
- File `webapp/child/child.js` (lines 244–313):
  ```javascript
  function toggleVoice() {
      ...
      if (isListening) { ... return; }
      ...
      recognition = new SpeechRecognition();
      recognition.lang = 'hi-IN';
      recognition.interimResults = false;

      recognition.onstart = async () => {
          isListening = true;
          ...
      };
      ...
      recognition.start();
  }
  ```
- File `webapp/child/child.js` (lines 189–242 & 119–137):
  ```javascript
  function animateTyping(element, text, speedMs = 25, onComplete = null) {
      if (!element) return;
      if (element.typingInterval) {
          clearInterval(element.typingInterval);
          element.typingInterval = null;
      }
      element.innerText = '';
      let i = 0;
      element.typingInterval = setInterval(() => { ... }, speedMs);
  }

  async function quickAction(text) {
      const captionSub = document.getElementById('caption-sub');
      captionSub.innerText = "Vadi is thinking...";
      ...
  }
  ```
- File `webapp/child/child.js` (lines 316–371):
  ```javascript
  async function speakReply(text) {
      ...
      animateTyping(captionSub, cleanText);
      setMouthState('speaking');
      if (currentAudio) { currentAudio.pause(); currentAudio = null; }
      ...
      currentAudio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
      ...
      await currentAudio.play();
  }
  ```

---

## 2. Logic Chain

1. **Voice Fallback Chain Verification**:
   - Observation 1.2 shows that `ElevenLabsTTSService` checks `if not settings.elevenlabs.api_key:` or catches HTTP errors in `except Exception as exc:`, delegating to `self.fallback_tts` (`KokoroTTSService`).
   - `KokoroTTSService` checks `if language == "pa":` or catches HTTP exceptions, delegating to `self.fallback_service` (`PiperTTSService`).
   - `PiperTTSService` executes local subprocess or returns `b"ERR_PIPER_TTS_FAILED"`.
   - Empirical tests in `test_fallback_empirical.py` confirmed 5/5 fallback paths pass.
   - **Performance Code Smell**: `PiperTTSService.synthesize` performs synchronous subprocess I/O (`process.communicate(timeout=3.0)`) inside an `async def` method on the main event loop.

2. **Web Audio API & Canvas Visualizer Edge Cases in `child.js`**:
   - **Edge Case 1 — Missing Audio Pause on Mic Trigger (Acoustic Feedback Leak)**:
     - In Observation 1.3, `toggleVoice()` initiates speech recognition and mic stream via `getUserMedia`.
     - However, `toggleVoice()` does NOT check or pause `currentAudio`.
     - If the child taps the microphone button while Vadi is speaking out loud, TTS audio continues playing through the speakers while the microphone starts listening, causing speaker audio to feed back into speech recognition.
   - **Edge Case 2 — Race Condition on Fast Toggling (`InvalidStateError`)**:
     - In Observation 1.3, `isListening` is updated to `true` ONLY inside `recognition.onstart`, which fires asynchronously after 200–500ms.
     - Rapidly clicking the mic button twice in quick succession evaluates `isListening` as `false` both times, instantiating a second `SpeechRecognition` instance and calling `recognition.start()` twice, throwing `DOMException: InvalidStateError: recognition has already started`.
   - **Edge Case 3 — Text Animation Timer Leak & State Collision in `animateTyping`**:
     - In Observation 1.3, `animateTyping` attaches `typingInterval` to the target DOM element.
     - `quickAction()` assigns `captionSub.innerText = "Vadi is thinking..."` directly without calling `clearInterval(captionSub.typingInterval)`.
     - If `animateTyping` is animating a long reply (e.g. 500 characters taking 12.5 seconds at 25ms/char) when `quickAction` or an error handler executes, the un-cleared `setInterval` continues appending characters from the old message onto `"Vadi is thinking..."`, resulting in garbled string concatenation.
   - **Edge Case 4 — Web Audio API User Gesture Autoplay Restriction**:
     - `getAudioContext()` is called inside `speakReply()`, which executes asynchronously inside the `fetch()` response handler rather than directly within a synchronous user gesture callback. Modern browsers flag this as an un-activated `AudioContext` and prevent `.resume()`.

---

## 3. Caveats

- **Network-Level LiveKit SFU Stream**: Verification was conducted using Mock and local HTTP/unit contracts; live WebRTC audio transport under real network packet loss/jitter was not simulated.
- No other caveats.

---

## 4. Conclusion & Verdict

**VERDICT**: **FAIL**

While the voice gateway backend service and unit tests (`pytest services/voice-gateway/tests/`) pass 100% (15/15 unit tests + 5/5 empirical fallback tests), the frontend implementation in `webapp/child/child.js` contains 3 critical/medium defects that break UX robustness:
1. **Audio Feedback Loop**: `toggleVoice()` fails to pause active `currentAudio` when mic listening starts.
2. **Fast-Toggle Race Condition**: `isListening` flag is not set synchronously in `toggleVoice()`, allowing double `recognition.start()` calls.
3. **Timer Leak / Text Corruption**: `quickAction()` resets `captionSub.innerText` without clearing active `captionSub.typingInterval`.

---

## 5. Verification Method

To independently verify these findings:

1. **Backend Tests**:
   ```bash
   py -m pytest services/voice-gateway/tests/
   py -m pytest .agents/challenger_m3_1/test_fallback_empirical.py
   ```
2. **Frontend Code Inspection**:
   - Open `webapp/child/child.js` at line 244 (`toggleVoice`), line 189 (`quickAction`), and line 119 (`animateTyping`).
   - Inspect `toggleVoice()` to verify `currentAudio.pause()` is missing.
   - Inspect line 270 inside `toggleVoice()` to verify `isListening` is assigned inside `onstart` rather than before `start()`.
   - Inspect line 193 inside `quickAction()` to verify `captionSub.innerText = "Vadi is thinking..."` does not clear `captionSub.typingInterval`.
