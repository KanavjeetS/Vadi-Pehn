"""
Verification script for webapp/child/child.js fixes in Milestone 3
"""
import re
from pathlib import Path

def test_child_js_fixes():
    js_path = Path(r"d:\Vadi Bhen\webapp\child\child.js")
    assert js_path.exists(), "child.js file must exist"
    content = js_path.read_text(encoding="utf-8")

    # 1. Verify Audio Feedback Loop Fix:
    # In toggleVoice(), check currentAudio.pause() and currentAudio.currentTime = 0 when starting mic listening
    assert "if (currentAudio) {" in content
    assert "currentAudio.pause();" in content
    assert "currentAudio.currentTime = 0;" in content

    # 2. Verify Fast-Toggle Race Condition Fix:
    # In toggleVoice(), set isListening = true synchronously before recognition.start()
    toggle_voice_match = re.search(r'function toggleVoice\(\)\s*\{([\s\S]*?)\n\}', content)
    assert toggle_voice_match is not None, "toggleVoice function must be defined"
    toggle_body = toggle_voice_match.group(1)

    # Confirm isListening = true appears before recognition.start() inside toggleVoice
    is_listening_pos = toggle_body.find("isListening = true;")
    rec_start_pos = toggle_body.find("recognition.start();")
    assert is_listening_pos != -1, "isListening = true must be set in toggleVoice"
    assert rec_start_pos != -1, "recognition.start() must be called in toggleVoice"
    assert is_listening_pos < rec_start_pos, "isListening = true must be set synchronously before recognition.start()"

    # 3. Verify Typing Animation Timer Leak Fix:
    # Check stopTypingAnimation function exists and clears typingInterval
    assert "function stopTypingAnimation(" in content
    assert "clearInterval(element.typingInterval);" in content
    assert "element.typingInterval = null;" in content

    # Check animateTyping clears typingInterval before starting new interval
    animate_typing_match = re.search(r'function animateTyping\([\s\S]*?\{([\s\S]*?)\n\}', content)
    assert animate_typing_match is not None, "animateTyping function must be defined"
    animate_body = animate_typing_match.group(1)
    assert "clearInterval(element.typingInterval)" in animate_body or "stopTypingAnimation(element)" in animate_body

    print("SUCCESS: All 3 edge cases in webapp/child/child.js verified successfully.")

if __name__ == "__main__":
    test_child_js_fixes()
