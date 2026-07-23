"""
Empirical verification script for challenger_m3_2
Tests webapp/child/child.js structure and rules.
"""
import re
import subprocess
from pathlib import Path

CHILD_JS_PATH = Path(r"d:\Vadi Bhen\webapp\child\child.js")

def test_audio_feedback_loop():
    content = CHILD_JS_PATH.read_text(encoding="utf-8")
    
    # Check toggleVoice for audio stopping
    toggle_voice_match = re.search(r'function toggleVoice\(\)\s*\{([\s\S]*?)\n\}', content)
    assert toggle_voice_match, "toggleVoice function not found"
    toggle_body = toggle_voice_match.group(1)
    
    assert "currentAudio.pause()" in toggle_body, "currentAudio.pause() missing in toggleVoice"
    assert "currentAudio.currentTime = 0" in toggle_body, "currentAudio.currentTime = 0 missing in toggleVoice"
    assert "currentAudio = null" in toggle_body, "currentAudio = null missing in toggleVoice"
    assert "stopVisualizer()" in toggle_body, "stopVisualizer() missing in toggleVoice"
    
    # Verify currentAudio cleanup happens BEFORE speech recognition start
    pause_idx = toggle_body.find("currentAudio.pause()")
    start_idx = toggle_body.find("recognition.start()")
    assert pause_idx != -1 and start_idx != -1 and pause_idx < start_idx, \
        "currentAudio cleanup must happen before recognition.start()"
    print("[PASS] Edge Case 1: Audio Feedback Loop remediation verified.")

def test_fast_toggle_race_condition():
    content = CHILD_JS_PATH.read_text(encoding="utf-8")
    
    toggle_voice_match = re.search(r'function toggleVoice\(\)\s*\{([\s\S]*?)\n\}', content)
    assert toggle_voice_match, "toggleVoice function not found"
    toggle_body = toggle_voice_match.group(1)
    
    # Check synchronous isListening = true setting
    assert "isListening = true;" in toggle_body, "isListening = true must be set synchronously in toggleVoice"
    
    sync_set_idx = toggle_body.find("isListening = true;")
    rec_new_idx = toggle_body.find("recognition = new SpeechRecognition()")
    assert sync_set_idx < rec_new_idx, "isListening = true must be set BEFORE new SpeechRecognition()"
    
    # Check try-catch around recognition.start()
    try_start_match = re.search(r'try\s*\{\s*recognition\.start\(\);\s*\}\s*catch\s*\((.*?)\)\s*\{([\s\S]*?)\}', toggle_body)
    assert try_start_match, "recognition.start() must be wrapped in a try-catch block"
    
    catch_body = try_start_match.group(2)
    assert "isListening = false;" in catch_body, "catch block must reset isListening = false"
    assert "stopMicStream()" in catch_body, "catch block must clean up mic stream"
    assert "stopVisualizer()" in catch_body, "catch block must clean up visualizer"
    print("[PASS] Edge Case 2: Fast-Toggle Race Condition remediation verified.")

def test_typing_animation_timer_leak():
    content = CHILD_JS_PATH.read_text(encoding="utf-8")
    
    stop_fn_match = re.search(r'function stopTypingAnimation\((.*?)\)\s*\{([\s\S]*?)\}', content)
    assert stop_fn_match, "stopTypingAnimation function not found"
    stop_body = stop_fn_match.group(2)
    
    assert "clearInterval(" in stop_body, "stopTypingAnimation must call clearInterval"
    assert "typingInterval = null" in stop_body, "stopTypingAnimation must clear typingInterval property"
    
    animate_fn_match = re.search(r'function animateTyping\((.*?)\)\s*\{([\s\S]*?)\}', content)
    assert animate_fn_match, "animateTyping function not found"
    animate_body = animate_fn_match.group(2)
    
    assert "clearInterval(" in animate_body, "animateTyping must clear pre-existing interval"
    assert ".typingInterval =" in animate_body, "animateTyping must store interval handle on element"
    print("[PASS] Edge Case 3: Typing Animation Timer Leak remediation verified.")

def test_pytest_voice_gateway():
    res = subprocess.run(["py", "-m", "pytest", r"services\voice-gateway\tests\\"], capture_output=True, text=True)
    assert res.returncode == 0, f"pytest failed:\n{res.stdout}\n{res.stderr}"
    assert "15 passed" in res.stdout, f"Expected 15 passed, got output:\n{res.stdout}"
    print("[PASS] Requirement 4: Pytest suite execution verified (15 passed).")

if __name__ == "__main__":
    test_audio_feedback_loop()
    test_fast_toggle_race_condition()
    test_typing_animation_timer_leak()
    test_pytest_voice_gateway()
    print("\nALL EMPIRICAL TESTS PASSED SUCCESSFULLY!")
