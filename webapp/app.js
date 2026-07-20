/* ==========================================================================
   Vadi-Pehn Platform Interactive Logic
   ========================================================================== */

let currentTurnCount = 1;
const MAX_TURNS = 20;

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
        const response = await fetch('/api/v1/turn', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test_desktop_token_123'
            },
            body: JSON.stringify({
                session_id: 'sess_desktop_001',
                tenant_id: '00000000-0000-0000-0000-000000000001',
                learner_id: '00000000-0000-0000-0000-000000000002',
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
            handleLocalTurnSimulation(messageText);
        }
    } catch (err) {
        handleLocalTurnSimulation(messageText);
    }
}

function handleLocalTurnSimulation(messageText) {
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

    appendMessage(reply, 'assistant', 'safe');
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
        await fetch('/api/v1/guardian/consent', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test_desktop_token_123'
            },
            body: JSON.stringify({
                tenant_id: '00000000-0000-0000-0000-000000000001',
                learner_id: '00000000-0000-0000-0000-000000000002',
                guardian_id: '00000000-0000-0000-0000-000000000003',
                consent_type: consentType,
                granted: isGranted
            })
        });
    } catch (e) {
        console.log("Consent toggle updated locally:", consentType, isGranted);
    }
}

async function simulateFileUpload() {
    const mode = document.getElementById('ocr-mode-select').value;
    const jsonView = document.getElementById('extracted-json-view');
    const ocrStep = document.getElementById('step-ocr');
    const ocrConfText = document.getElementById('ocr-confidence-text');

    let fileName = "report_card_synthetic.png";
    let fileData = "synthetic_image_bytes";
    let expectedGrade = "A";

    if (mode === "low_conf") {
        fileData = "low_conf_image_data";
    } else if (mode === "grade_mismatch") {
        expectedGrade = "A";
    }

    try {
        const res = await fetch('/internal/v1/documents/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tenant_id: '00000000-0000-0000-0000-000000000001',
                learner_id: '00000000-0000-0000-0000-000000000002',
                file_name: fileName,
                file_bytes_base64: fileData,
                in_app_expected_grade: expectedGrade
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
            simulateLocalDocumentOutput(mode);
        }
    } catch (e) {
        simulateLocalDocumentOutput(mode);
    }
}

function simulateLocalDocumentOutput(mode) {
    const jsonView = document.getElementById('extracted-json-view');
    const ocrConfText = document.getElementById('ocr-confidence-text');

    if (mode === "low_conf") {
        const out = {
            document_id: "doc_synth_99",
            redaction_verified: true,
            ocr_confidence: 0.72,
            requires_discrepancy_review: true,
            discrepancy_reasons: ["OCR confidence (0.72) below minimum threshold of 0.85"]
        };
        jsonView.innerText = JSON.stringify(out, null, 2);
        ocrConfText.innerText = "Confidence: 0.72 | Routed to Discrepancy Queue";
        updateDiscrepancyTable(out);
    } else if (mode === "grade_mismatch") {
        const out = {
            document_id: "doc_synth_88",
            redaction_verified: true,
            ocr_confidence: 0.92,
            requires_discrepancy_review: true,
            discrepancy_reasons: ["Grade mismatch: Extracted 'B' vs Expected 'A'"]
        };
        jsonView.innerText = JSON.stringify(out, null, 2);
        ocrConfText.innerText = "Confidence: 0.92 | Grade Mismatch Flagged";
        updateDiscrepancyTable(out);
    } else {
        const out = {
            document_id: "doc_synth_01",
            redaction_verified: true,
            ocr_confidence: 0.94,
            student_name: "Learner Alex",
            overall_grade: "A",
            subjects: { "Math": "95", "Science": "92" },
            requires_discrepancy_review: false
        };
        jsonView.innerText = JSON.stringify(out, null, 2);
        ocrConfText.innerText = "Confidence: 0.94 | VERIFIED PASS";
    }
}

function updateDiscrepancyTable(data) {
    const tbody = document.getElementById('discrepancy-table-body');
    tbody.innerHTML = `
        <tr>
            <td>1</td>
            <td><code>${data.document_id || 'doc_synth_99'}</code></td>
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
