/* Vadi-Pehn Kid Companion & Avatar Controller */

let isListening = false;
let recognition = null;
let currentAudio = null;
let currentMood = 'Curious';
let authToken = localStorage.getItem('vadi_access_token') || sessionStorage.getItem('vadi_access_token') || localStorage.getItem('access_token') || sessionStorage.getItem('access_token') || '';
let tenantId = localStorage.getItem('vadi_tenant_id') || sessionStorage.getItem('vadi_tenant_id') || localStorage.getItem('tenant_id') || sessionStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000001';
let learnerId = localStorage.getItem('vadi_learner_id') || sessionStorage.getItem('vadi_learner_id') || localStorage.getItem('learner_id') || sessionStorage.getItem('learner_id') || '00000000-0000-0000-0000-000000000003';
let ageBand = parseInt(localStorage.getItem('vadi_age_band') || sessionStorage.getItem('vadi_age_band') || '2', 10);

// ── Web Audio API Visualizer State ──────────────────────────────────────────
let audioCtx = null;
let analyser = null;
let animFrameId = null;
let micStream = null;
let micSource = null;
let audioMediaSource = null;

function getAudioContext() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64;
    }
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    return { audioCtx, analyser };
}

function startVisualizer(sourceNode, connectDestination = false) {
    const { audioCtx, analyser } = getAudioContext();
    if (sourceNode) {
        try {
            sourceNode.connect(analyser);
            if (connectDestination) {
                analyser.connect(audioCtx.destination);
            }
        } catch (e) {
            console.warn('Audio source connection note:', e);
        }
    }

    const canvas = document.getElementById('audio-waveform-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
        animFrameId = requestAnimationFrame(draw);
        analyser.getByteFrequencyData(dataArray);

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const barWidth = (canvas.width / bufferLength) * 1.4;
        let x = 4;

        for (let i = 0; i < bufferLength; i++) {
            const barHeight = Math.max(4, (dataArray[i] / 255) * (canvas.height - 8));
            const gradient = ctx.createLinearGradient(0, canvas.height, 0, 0);
            gradient.addColorStop(0, '#7c3aed');
            gradient.addColorStop(0.5, '#00bbf9');
            gradient.addColorStop(1, '#ec4899');

            ctx.fillStyle = gradient;
            ctx.beginPath();
            if (ctx.roundRect) {
                ctx.roundRect(x, canvas.height - barHeight, barWidth - 2, barHeight, 4);
            } else {
                ctx.fillRect(x, canvas.height - barHeight, barWidth - 2, barHeight);
            }
            ctx.fill();

            x += barWidth + 2;
        }
    }

    if (animFrameId) cancelAnimationFrame(animFrameId);
    draw();
}

function stopVisualizer() {
    if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
    }
    drawIdleWaveform();
}

function drawIdleWaveform() {
    const canvas = document.getElementById('audio-waveform-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    ctx.strokeStyle = 'rgba(124, 58, 237, 0.4)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    const centerY = canvas.height / 2;
    ctx.moveTo(0, centerY);
    const time = Date.now() * 0.003;
    for (let x = 0; x < canvas.width; x += 6) {
        const y = centerY + Math.sin(x * 0.05 + time) * 4;
        ctx.lineTo(x, y);
    }
    ctx.stroke();
}

function stopMicStream() {
    if (micStream) {
        micStream.getTracks().forEach(track => track.stop());
        micStream = null;
    }
    if (micSource) {
        try { micSource.disconnect(); } catch (e) {}
        micSource = null;
    }
}

// ── Theme Switcher ────────────────────────────────────────────────────────
function toggleTheme() {
    document.body.classList.toggle('light-theme');
    const icon = document.getElementById('theme-icon');
    const isLight = document.body.classList.contains('light-theme');
    if (icon) icon.innerText = isLight ? '☀️' : '🌙';
}

// ── Mood Selector ────────────────────────────────────────────────────────
function setMood(mood, element) {
    currentMood = mood;
    document.querySelectorAll('.mood-chip').forEach(el => el.classList.remove('selected'));
    if (element) element.classList.add('selected');
}

// ── Staggered Slide-In Chat Bubbles Renderer ─────────────────────────────
function addChatBubble(sender, text) {
    const container = document.getElementById('chat-bubbles-container');
    if (!container) return;

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender === 'user' ? 'user-bubble' : 'vadi-bubble'}`;
    bubble.innerText = `${sender === 'user' ? 'You' : 'Vadi'}: ${text}`;

    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
}

// ── Avatar States & Eye Blinking ─────────────────────────────────────────
function setMouthState(state) {
    const mouth = document.getElementById('vadi-mouth');
    const aura = document.getElementById('aura-ring');
    if (!mouth) return;

    if (state === 'speaking') {
        mouth.setAttribute('d', 'M82 122 Q100 144 118 122 Q100 132 82 122Z');
        mouth.setAttribute('fill', '#ffffff');
        if (aura) aura.style.background = 'radial-gradient(circle, rgba(236, 72, 153, 0.6) 0%, rgba(124, 58, 237, 0.0) 70%)';
    } else if (state === 'listening') {
        mouth.setAttribute('d', 'M86 124 Q100 130 114 124');
        mouth.setAttribute('fill', 'none');
        if (aura) aura.style.background = 'radial-gradient(circle, rgba(0, 187, 249, 0.6) 0%, rgba(124, 58, 237, 0.0) 70%)';
    } else {
        mouth.setAttribute('d', 'M82 122 Q100 138 118 122');
        mouth.setAttribute('fill', 'none');
        if (aura) aura.style.background = 'radial-gradient(circle, rgba(124, 58, 237, 0.4) 0%, rgba(236, 72, 153, 0.0) 70%)';
    }
}

// Eye Blink Animation Loop
(function initEyeBlinking() {
    setInterval(() => {
        const pupilL = document.getElementById('pupil-left');
        const pupilR = document.getElementById('pupil-right');
        if (pupilL && pupilR) {
            pupilL.style.transform = 'scaleY(0.1)';
            pupilR.style.transform = 'scaleY(0.1)';
            setTimeout(() => {
                pupilL.style.transform = 'scaleY(1)';
                pupilR.style.transform = 'scaleY(1)';
            }, 180);
        }
    }, 4500);
})();

// Ambient Star Canvas Particle System
(function initStars() {
    const canvas = document.getElementById('star-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let width, height, stars = [];

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    }
    window.addEventListener('resize', resize);
    resize();

    for (let i = 0; i < 50; i++) {
        stars.push({
            x: Math.random() * width,
            y: Math.random() * height,
            size: Math.random() * 2 + 1,
            alpha: Math.random(),
            speed: Math.random() * 0.02 + 0.005
        });
    }

    function animate() {
        ctx.clearRect(0, 0, width, height);
        stars.forEach(s => {
            s.alpha += s.speed;
            if (s.alpha > 1 || s.alpha < 0) s.speed = -s.speed;
            ctx.fillStyle = `rgba(255, 255, 255, ${Math.abs(s.alpha)})`;
            ctx.beginPath();
            ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
            ctx.fill();
        });
        requestAnimationFrame(animate);
    }
    animate();
})();

// ── Typing Animation & Indicator ─────────────────────────────────────────
function stopTypingAnimation(element) {
    if (element && element.typingInterval) {
        clearInterval(element.typingInterval);
        element.typingInterval = null;
    }
}

function animateTyping(element, text, speedMs = 25, onComplete = null) {
    if (!element) return;
    stopTypingAnimation(element);
    element.textContent = '';
    let i = 0;
    element.typingInterval = setInterval(() => {
        if (i < text.length) {
            element.textContent += text.charAt(i);
            i++;
        } else {
            stopTypingAnimation(element);
            if (onComplete) onComplete();
        }
    }, speedMs);
}

// ── Auth Initialization ───────────────────────────────────────────────────
async function initAuth() {
    try {
        if (!authToken) {
            const res = await fetch('/api/v1/auth/guest', { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                authToken = data.access_token;
                tenantId = data.tenant_id;
                learnerId = data.learner_id;
                localStorage.setItem('vadi_access_token', authToken);
                localStorage.setItem('vadi_tenant_id', tenantId);
                localStorage.setItem('vadi_learner_id', learnerId);
            } else {
                console.error(`Guest auth failed with status ${res.status}`);
            }
        }
    } catch (e) {
        console.error('Guest auth connection error:', e);
    }
    drawIdleWaveform();
}

function tapCharacter() {
    quickAction("Namaste Vadi! What cool topic are we exploring today?");
}

async function quickAction(text) {
    const captionSub = document.getElementById('caption-sub');
    stopTypingAnimation(captionSub);

    // Render user speech bubble
    addChatBubble('user', text);
    
    captionSub.innerHTML = `Vadi is thinking <span class="typing-indicator"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span>`;
    setMouthState('listening');

    try {
        if (!authToken) await initAuth();

        const res = await fetch('/api/v1/turn', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`,
                'X-Tenant-ID': tenantId
            },
            body: JSON.stringify({
                session_id: 'sess_' + Math.random().toString(36).substring(2, 10),
                tenant_id: tenantId,
                learner_id: learnerId,
                age_band: ageBand,
                message_text: text,
                language: 'hi',
                mood: currentMood
            })
        });

        if (res.ok) {
            const data = await res.json();
            if (data.safety_verdict && data.safety_verdict !== 'safe') {
                const safetyMsg = "Safety check triggered. Let's talk about something positive or ask a guardian for help!";
                addChatBubble('vadi', safetyMsg);
                captionSub.innerText = "Safety check triggered.";
                setMouthState('idle');
                return;
            }
            const reply = data.final_reply || "Main tumhare saath hoon! Let's explore together!";
            addChatBubble('vadi', reply);
            await speakReply(reply);
        } else {
            throw new Error(`Turn request failed with status ${res.status}`);
        }
    } catch (e) {
        console.error('Turn execution error:', e);
        // Fail-closed safety behavior per PRD
        const failClosedMsg = "Connection or safety check interrupted. Please ask your guardian or try again later.";
        addChatBubble('vadi', failClosedMsg);
        captionSub.innerText = "Connection interrupted.";
        setMouthState('idle');
    }
}

function toggleVoice() {
    const btn = document.getElementById('mic-trigger-btn');
    const ring = document.getElementById('mic-pulsing-ring');
    const captionSub = document.getElementById('caption-sub');

    if (isListening) {
        if (recognition) {
            try { recognition.stop(); } catch (e) {}
        }
        isListening = false;
        if (btn) btn.classList.remove('listening');
        if (ring) ring.classList.remove('active');
        stopMicStream();
        stopVisualizer();
        if (captionSub) captionSub.innerText = "Tap me or the mic button below to talk!";
        setMouthState('idle');
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        if (captionSub) captionSub.innerText = "Microphone input not supported in this browser. Please tap an option below!";
        return;
    }

    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        currentAudio = null;
        stopVisualizer();
    }

    isListening = true;
    recognition = new SpeechRecognition();
    recognition.lang = 'hi-IN';
    recognition.interimResults = false;

    recognition.onstart = async () => {
        isListening = true;
        if (btn) btn.classList.add('listening');
        if (ring) ring.classList.add('active');
        if (captionSub) captionSub.innerText = "Listening... Speak now!";
        setMouthState('listening');

        try {
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const { audioCtx, analyser } = getAudioContext();
                micSource = audioCtx.createMediaStreamSource(micStream);
                startVisualizer(micSource, false);
            } else {
                startVisualizer(null, false);
            }
        } catch (err) {
            console.warn('Microphone visualization fallback active:', err);
            startVisualizer(null, false);
        }
    };

    recognition.onresult = async (event) => {
        const transcript = event.results[0][0].transcript.trim();
        isListening = false;
        if (btn) btn.classList.remove('listening');
        if (ring) ring.classList.remove('active');
        stopMicStream();
        stopVisualizer();
        
        await quickAction(transcript);
    };

    recognition.onerror = (event) => {
        console.warn("Speech recognition error:", event.error);
        isListening = false;
        if (btn) btn.classList.remove('listening');
        if (ring) ring.classList.remove('active');
        stopMicStream();
        stopVisualizer();
        if (captionSub) captionSub.innerText = "Tap me or the mic button below to talk!";
        setMouthState('idle');
    };

    try {
        recognition.start();
    } catch (err) {
        console.warn("Failed to start speech recognition:", err);
        isListening = false;
        if (btn) btn.classList.remove('listening');
        if (ring) ring.classList.remove('active');
        stopMicStream();
        stopVisualizer();
        if (captionSub) captionSub.innerText = "Tap me or the mic button below to talk!";
        setMouthState('idle');
    }
}

async function speakReply(text) {
    const captionSub = document.getElementById('caption-sub');
    const cleanText = text.replace(/Vadi:\s*/gi, '').replace(/\(.*?\)/gi, '').trim();
    
    animateTyping(captionSub, cleanText);
    setMouthState('speaking');

    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
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
                currentAudio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
                
                try {
                    const { audioCtx, analyser } = getAudioContext();
                    audioMediaSource = audioCtx.createMediaElementSource(currentAudio);
                    startVisualizer(audioMediaSource, true);
                } catch (e) {
                    console.warn('MediaElementSource visualizer setup note:', e);
                }

                currentAudio.onended = () => {
                    setMouthState('idle');
                    stopVisualizer();
                };
                currentAudio.onerror = () => {
                    console.error('Audio playback error');
                    setMouthState('idle');
                    stopVisualizer();
                };
                await currentAudio.play();
                return;
            }
        }
    } catch (e) {
        console.error('TTS streaming error:', e);
    }

    if (captionSub) {
        stopTypingAnimation(captionSub);
        captionSub.innerText = `${cleanText}`;
    }
    setMouthState('idle');
    stopVisualizer();
}

window.addEventListener('DOMContentLoaded', () => {
    initAuth();
});
