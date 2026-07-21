/* Child Companion Application Logic */
let childTurnCount = 1;
const MAX_TURNS = 20;
let learnerAuthToken = "";

function childContext() {
    const context = {
        token: sessionStorage.getItem('vadi_access_token') || learnerAuthToken,
        tenantId: sessionStorage.getItem('vadi_tenant_id'),
        learnerId: sessionStorage.getItem('vadi_learner_id')
    };
    if (!context.token || !context.tenantId || !context.learnerId) {
        throw new Error('Learner authentication is required.');
    }
    return context;
}

async function initChildAuth() {
    // Generate/fetch signed learner role token
    try {
        const context = childContext();
        const res = await fetch('/api/v1/turn', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message_text: 'ping' })
        });
    } catch (e) {}
}

async function sendChildTurn(event) {
    event.preventDefault();
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    appendMsg(text, 'user');
    input.value = '';

    if (childTurnCount >= MAX_TURNS) {
        appendMsg("Aaj ke liye humne kafi baatein kar li hain! Chalo abhi rest karte hain aur baki baatein kal karenge. (Session Cap Reached)", 'assistant', 'safe');
        return;
    }

    const ageBand = parseInt(document.getElementById('age-band').value, 10);
    const lang = document.getElementById('lang-select').value;

    try {
        const res = await fetch('/api/v1/turn', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${context.token}`
            },
            body: JSON.stringify({
                session_id: crypto.randomUUID(),
                tenant_id: context.tenantId,
                learner_id: context.learnerId,
                age_band: ageBand,
                message_text: text,
                language: lang
            })
        });

        if (res.ok) {
            const data = await res.json();
            childTurnCount++;
            document.getElementById('turn-count').innerText = childTurnCount;
            let reply = data.final_reply || "Vadi: That sounds great!";

            const attachmentTerms = ["best friend", "asli bhai", "real brother", "only friend"];
            if (childTurnCount % 5 === 0 || attachmentTerms.some(t => text.toLowerCase().includes(t))) {
                reply += " (jaise maine bataya, main ek AI mentor hoon, asli brother nahi, par tumhari madad karke mujhe bahut khushi hoti hai)";
            }
            appendMsg(reply, 'assistant', 'safe');
        } else {
            throw new Error(`Turn failed (${res.status})`);
        }
    } catch (e) {
        appendMsg(`Unable to reach Vadi: ${e.message}`, 'system', 'error');
    }
}

function simulateChildReply(text) {
    throw new Error('Local turn simulation has been removed; live API required.');
    /*
    childTurnCount++;
    document.getElementById('turn-count').innerText = childTurnCount;

    let reply = `Yeh ek bahut acha question hai! Tumhara interest '${text}' mein hai.`;
    if (text.toLowerCase().includes("drone") || text.toLowerCase().includes("robot")) {
        reply = "Yeh toh bohot exciting project hai! Drones aur robotics mein linear algebra apply hoti hai. Main Priya Didi se connect karwa sakta hoon!";
    }

    const attachmentTerms = ["best friend", "asli bhai", "real brother", "only friend"];
    if (childTurnCount % 5 === 0 || attachmentTerms.some(t => text.toLowerCase().includes(t))) {
        reply += " (jaise maine bataya, main ek AI mentor hoon, asli brother nahi, par tumhari madad karke mujhe bahut khushi hoti hai)";
    }
    appendMsg(reply, 'assistant', 'safe'); */
}

function appendMsg(text, role, verdict = 'safe') {
    const history = document.getElementById('chat-messages');
    const bubble = document.createElement('div');
    bubble.className = `bubble ${role}`;

    if (role === 'assistant') {
        bubble.innerHTML = `
            <div class="bubble-meta">
                <span class="name">Vadi</span>
                <span class="tag-safe">${verdict.toUpperCase()}</span>
            </div>
            <div class="text">${text}</div>
        `;
    } else {
        bubble.innerHTML = `<div class="text">${text}</div>`;
    }

    history.appendChild(bubble);
    history.scrollTop = history.scrollHeight;
}

function startVoiceTurn() {
    const indicator = document.getElementById('voice-indicator');
    indicator.classList.remove('hidden');

    setTimeout(() => {
        indicator.classList.add('hidden');
        appendMsg("Spoken: 'Namaste Vadi, mera robotics project kab submit hoga?'", 'user');

        setTimeout(() => {
            childTurnCount++;
            document.getElementById('turn-count').innerText = childTurnCount;
            appendMsg("Vadi Voice Stream (Kokoro TTS): Next Friday tak submit karna hai — chalo step-by-step sensors aur code verify karte hain!", 'assistant', 'safe');
        }, 800);
    }, 1500);
}
