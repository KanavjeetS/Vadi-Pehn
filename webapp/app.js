/* ==========================================================================
   Vadi-Pehn Platform Interactive Logic
   ========================================================================== */

let currentTurnCount = 1;
const MAX_TURNS = 20;

function authenticatedContext() {
    const context = {
        token: sessionStorage.getItem('vadi_access_token'),
        tenantId: sessionStorage.getItem('vadi_tenant_id'),
        learnerId: sessionStorage.getItem('vadi_learner_id')
    };
    if (!context.token || !context.tenantId || !context.learnerId) {
        throw new Error('Sign in and select a learner before starting a turn.');
    }
    return context;
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

    const activeTab = document.getElementById(`tab-${tabId}`);
    const activeNav = document.getElementById(`nav-${tabId}`);

    if (activeTab) activeTab.classList.add('active');
    if (activeNav) activeNav.classList.add('active');
}

async function handleSendTurn(event) {
    event.preventDefault();
    const inputEl = document.getElementById('user-input');
    const messageText = inputEl.value.trim();
    if (!messageText) return;

    // Append user message
    appendMessage(messageText, 'user');
    inputEl.value = '';

    // Check turn count cap
    if (currentTurnCount >= MAX_TURNS) {
        appendMessage("Aaj ke liye humne kafi baatein kar li hain! Chalo abhi rest karte hain aur baki baatein kal karenge. (Session Cap Reached)", 'assistant', 'safe');
        return;
    }

    const ageBand = parseInt(document.getElementById('age-band-select').value, 10);
    const language = document.getElementById('lang-select').value;

    try {
        const context = authenticatedContext();
        const response = await fetch('/api/v1/turn', {
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
                message_text: messageText,
                language: language
            })
        });

        if (response.ok) {
            const data = await response.json();
            currentTurnCount++;
            document.getElementById('turn-count').innerText = currentTurnCount;

            let replyText = data.final_reply || data.reply_text || "Vadi: That sounds great!";
            
            // Check for attachment terms or 5th turn disclosure (PRD §4.1)
            const attachmentTerms = ["best friend", "asli bhai", "real brother", "only friend"];
            if (currentTurnCount % 5 === 0 || attachmentTerms.some(t => messageText.toLowerCase().includes(t))) {
                replyText += " (jaise maine bataya, main ek AI mentor hoon, asli brother nahi, par tumhari madad karke mujhe bahut khushi hoti hai)";
            }

            appendMessage(replyText, 'assistant', data.safety_verdict || 'safe');
        } else {
            // Fallback for local offline simulation
            throw new Error(`Turn failed (${response.status})`);
        }
    } catch (err) {
        appendMessage(`Unable to reach Vadi: ${err.message}`, 'system', 'error');
    }
}

function handleLocalTurnSimulation(messageText) {
    throw new Error('Local turn simulation has been removed; live API required.');
    /*
    currentTurnCount++;
    document.getElementById('turn-count').innerText = currentTurnCount;

    let reply = "";
    if (messageText.toLowerCase().includes("drone") || messageText.toLowerCase().includes("robot")) {
        reply = "Yeh toh bohot exciting project hai! Robotics aur drones mein linear algebra aur mechanical sensors apply hote hain. Mujhe Dr. Priya Sharma se poochne do ki unka kya suggestion hai!";
    } else if (messageText.toLowerCase().includes("bura") || messageText.toLowerCase().includes("sad")) {
        reply = "main sun raha hoon. jo tum share kar rahe ho woh bahut bhari baat hai. please kisi bade pe bharosa karo — teacher, ghar mein koi, ya helpline. tum akele nahi ho.";
    } else {
        reply = `Yeh ek bahut acha question hai! Tumhara interest '${messageText}' mein hai, yeh jaan kar bohot accha laga.`;
    }

    const attachmentTerms = ["best friend", "asli bhai", "real brother", "only friend"];
    if (currentTurnCount % 5 === 0 || attachmentTerms.some(t => messageText.toLowerCase().includes(t))) {
        reply += " (jaise maine bataya, main ek AI mentor hoon, asli brother nahi, par tumhari madad karke mujhe bahut khushi hoti hai)";
    }

    appendMessage(reply, 'assistant', 'safe'); */
}

function appendMessage(text, role, verdict = 'safe') {
    const history = document.getElementById('chat-history');
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${role}`;

    if (role === 'assistant') {
        bubble.innerHTML = `
            <div class="bubble-header">
                <span class="sender-name">Vadi</span>
                <span class="verdict-tag ${verdict}">${verdict.toUpperCase()}</span>
            </div>
            <div class="bubble-text">${text}</div>
        `;
    } else {
        bubble.innerHTML = `<div class="bubble-text">${text}</div>`;
    }

    history.appendChild(bubble);
    history.scrollTop = history.scrollHeight;
}

function triggerVoiceTurn() {
    const indicator = document.getElementById('voice-indicator');
    indicator.classList.remove('hidden');

    setTimeout(() => {
        indicator.classList.add('hidden');
        appendMessage("Simulated Spoken Audio: 'Namaste Vadi, mera math test next week hai.'", 'user');
        
        setTimeout(() => {
            currentTurnCount++;
            document.getElementById('turn-count').innerText = currentTurnCount;
            appendMessage("Vadi Voice Stream (Kokoro TTS): All the best for your Math test! Linear algebra aur fractions revise kar lo — main tumhare saath practice karwa sakta hoon.", 'assistant', 'safe');
        }, 800);
    }, 1500);
}

async function toggleConsent(consentType, isGranted) {
    try {
        const token = sessionStorage.getItem('vadi_access_token');
        if (!token) throw new Error('Sign in before changing consent');
        await fetch('/api/v1/guardian/consent', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                tenant_id: sessionStorage.getItem('vadi_tenant_id'),
                learner_id: sessionStorage.getItem('vadi_learner_id'),
                guardian_id: sessionStorage.getItem('vadi_guardian_id'),
                consent_type: consentType,
                granted: isGranted
            })
        });
    } catch (e) {
        console.error('Consent update failed:', e);
    }
}

async function simulateFileUpload() {
    const mode = document.getElementById('ocr-mode-select').value;
    const jsonView = document.getElementById('extracted-json-view');
    const ocrStep = document.getElementById('step-ocr');
    const ocrConfText = document.getElementById('ocr-confidence-text');

    const fileInput = document.getElementById('document-file-input');
    const file = fileInput?.files?.[0];
    const token = sessionStorage.getItem('vadi_access_token');
    if (!file || !token) {
        ocrConfText.innerText = 'Sign in and choose a document before uploading.';
        return;
    }
    const fileData = await fileToBase64(file);

    try {
        const res = await fetch('/api/v1/documents/upload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                tenant_id: sessionStorage.getItem('vadi_tenant_id'),
                learner_id: sessionStorage.getItem('vadi_learner_id'),
                file_name: file.name,
                file_bytes_base64: fileData,
                in_app_expected_grade: document.getElementById('expected-grade')?.value || null
            })
        });

        if (res.ok) {
            const data = await res.json();
            jsonView.innerText = JSON.stringify(data, null, 2);
            ocrConfText.innerText = `Confidence: ${data.ocr_confidence} | Mask Verified: ${data.redaction_verified}`;
            
            if (data.requires_discrepancy_review) {
                updateDiscrepancyTable(data);
            }
        } else {
            throw new Error(`Upload failed (${res.status})`);
        }
    } catch (e) {
        ocrConfText.innerText = `Upload failed: ${e.message}`;
        console.error(e);
    }
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

function updateDiscrepancyTable(data) {
    const tbody = document.getElementById('discrepancy-table-body');
    tbody.innerHTML = `
        <tr>
            <td>1</td>
            <td><code>${data.document_id || 'unassigned'}</code></td>
            <td>overall_grade</td>
            <td>B</td>
            <td>A</td>
            <td><span class="badge-tag alert">OPEN REVIEW</span></td>
        </tr>
    `;
}

function acknowledgeIncident(incId) {
    alert(`Incident ${incId} acknowledged by on-call reviewer. SLA status cleared.`);
}
