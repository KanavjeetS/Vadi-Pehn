/* Vadi-Pehn Kid Companion Controller */

let isListening = false;
let recognition = null;
let currentAudio = null;
let authToken = sessionStorage.getItem('vadi_access_token') || '';
let tenantId = sessionStorage.getItem('vadi_tenant_id') || '00000000-0000-0000-0000-000000000001';
let learnerId = sessionStorage.getItem('vadi_learner_id') || '00000000-0000-0000-0000-000000000002';

async function initAuth() {
    try {
        if (!authToken) {
            const res = await fetch('/api/v1/auth/guest', { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                authToken = data.access_token;
                tenantId = data.tenant_id;
                learnerId = data.learner_id;
                sessionStorage.setItem('vadi_access_token', authToken);
                sessionStorage.setItem('vadi_tenant_id', tenantId);
                sessionStorage.setItem('vadi_learner_id', learnerId);
            }
        }
    } catch (e) {
        console.warn('Guest auth auto-provisioning fallback.');
    }
}

function setMouthState(state) {
    const mouth = document.getElementById('vadi-mouth');
    if (!mouth) return;

    if (state === 'speaking') {
        mouth.setAttribute('d', 'M82 122 Q100 142 118 122 Q100 134 82 122Z');
        mouth.setAttribute('fill', '#ffffff');
    } else if (state === 'listening') {
        mouth.setAttribute('d', 'M88 126 Q100 130 112 126');
        mouth.setAttribute('fill', 'none');
    } else {
        mouth.setAttribute('d', 'M82 122 Q100 138 118 122');
        mouth.setAttribute('fill', 'none');
    }
}

function tapCharacter() {
    quickAction("Yay! Tumne mujhe tap kiya!");
}

async function quickAction(text) {
    const captionSub = document.getElementById('caption-sub');
    const bubble = document.getElementById('transcript-bubble');
    
    captionSub.innerText = "Vadi is thinking...";
    bubble.style.display = 'block';
    bubble.innerText = `You: ${text}`;
    setMouthState('listening');

    try {
        if (!authToken) await initAuth();

        const res = await fetch('/api/v1/turn', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify({
                session_id: 'sess_' + Math.random().toString(36).substring(2, 10),
                tenant_id: tenantId,
                learner_id: learnerId,
                age_band: 2,
                message_text: text,
                language: 'hi'
            })
        });

        if (res.ok) {
            const data = await res.json();
            const reply = data.final_reply || "Vadi: Main tumhare saath hoon!";
            bubble.innerText = reply;
            speakReply(reply);
        } else {
            throw new Error(`Turn status ${res.status}`);
        }
    } catch (e) {
        const fallback = `Vadi: Main tumhari baat sun raha hoon! Tumne kaha '${text}'. Aao milkar seekhte hain!`;
        bubble.innerText = fallback;
        speakReply(fallback);
    }
}

function toggleVoice() {
    const btn = document.getElementById('mic-trigger-btn');
    const captionSub = document.getElementById('caption-sub');

    if (isListening) {
        if (recognition) recognition.stop();
        isListening = false;
        btn.classList.remove('listening');
        captionSub.innerText = "Tap me or the button below to talk";
        setMouthState('idle');
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        quickAction("Namaste Vadi!");
        return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = 'hi-IN';
    recognition.interimResults = false;

    recognition.onstart = () => {
        isListening = true;
        btn.classList.add('listening');
        captionSub.innerText = "Listening... speak now!";
        setMouthState('listening');
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        isListening = false;
        btn.classList.remove('listening');
        quickAction(transcript);
    };

    recognition.onerror = () => {
        isListening = false;
        btn.classList.remove('listening');
        captionSub.innerText = "Tap me or the button below to talk";
        setMouthState('idle');
    };

    recognition.start();
}

// ── ElevenLabs Low-Latency Streaming Audio Synthesis ───────────────────────
async function speakReply(text) {
    const captionSub = document.getElementById('caption-sub');
    const cleanText = text.replace(/Vadi:\s*/gi, '').replace(/\(.*?\)/gi, '').strip ? text.replace(/Vadi:\s*/gi, '').replace(/\(.*?\)/gi, '').strip() : text.replace(/Vadi:\s*/gi, '').replace(/\(.*?\)/gi, '');
    captionSub.innerText = cleanText;
    setMouthState('speaking');

    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }

    try {
        const res = await fetch('/api/v1/voice/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: cleanText, language: 'hi' })
        });

        if (res.ok) {
            const data = await res.json();
            if (data.audio_base64) {
                // Play live synthesized ElevenLabs audio stream!
                currentAudio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
                currentAudio.onended = () => setMouthState('idle');
                currentAudio.onerror = () => fallbackSpeechSynthesis(cleanText);
                await currentAudio.play();
                return;
            }
        }
    } catch (e) {
        console.warn('ElevenLabs API streaming error, falling back to browser synth:', e);
    }

    fallbackSpeechSynthesis(cleanText);
}

function fallbackSpeechSynthesis(text) {
    if (!('speechSynthesis' in window)) {
        setTimeout(() => setMouthState('idle'), 3000);
        return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'hi-IN';
    utterance.rate = 0.95;
    utterance.pitch = 1.0;

    utterance.onend = () => setMouthState('idle');
    utterance.onerror = () => setMouthState('idle');

    window.speechSynthesis.speak(utterance);
}

window.addEventListener('DOMContentLoaded', () => {
    initAuth();
});
