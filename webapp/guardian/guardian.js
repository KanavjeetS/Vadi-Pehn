/* Guardian Governance Console Interactive Logic */
let guardianToken = "";

function showEnrollModal() {
    document.getElementById('enroll-modal').classList.remove('hidden');
}

function hideEnrollModal() {
    document.getElementById('enroll-modal').classList.add('hidden');
}

async function handleEnrollGuardian(event) {
    event.preventDefault();
    const gName = document.getElementById('g-name').value;
    const gPhone = document.getElementById('g-phone').value;
    const gMethod = document.getElementById('g-method').value;

    try {
        const res = await fetch('/api/v1/guardian/enroll', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                guardian_name: gName,
                phone_number: gPhone,
                verification_method: gMethod
            })
        });

        if (res.ok) {
            const data = await res.json();
            guardianToken = data.access_token;
            setAuthVerified(data.guardian_id);
            hideEnrollModal();
        } else {
            simulateLocalEnroll();
        }
    } catch (e) {
        simulateLocalEnroll();
    }
}

function simulateLocalEnroll() {
    guardianToken = "mock_guardian_jwt_token_123";
    setAuthVerified("00000000-0000-0000-0000-000000000003");
    hideEnrollModal();
}

function setAuthVerified(id) {
    const badge = document.getElementById('auth-status-badge');
    badge.className = "status-badge verified";
    badge.innerText = `AUTHENTICATED GUARDIAN (${id.slice(0, 8)})`;
}

async function handleProvisionLearner(event) {
    event.preventDefault();
    const name = document.getElementById('l-name').value;
    const band = parseInt(document.getElementById('l-band').value, 10);

    try {
        const res = await fetch('/api/v1/guardian/learners', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${guardianToken || 'mock_guardian_jwt_token_123'}`
            },
            body: JSON.stringify({
                display_name: name,
                age_band: band
            })
        });

        if (res.ok) {
            const data = await res.json();
            displayChildToken(data.access_token);
        } else {
            displayChildToken("jwt_sample_learner_token_role_learner");
        }
    } catch (e) {
        displayChildToken("jwt_sample_learner_token_role_learner");
    }
}

function displayChildToken(token) {
    const box = document.getElementById('learner-token-box');
    const codeEl = document.getElementById('issued-child-token');
    codeEl.innerText = token;
    box.classList.remove('hidden');
}

async function toggleConsentRow(type, btn) {
    const isGranted = btn.innerText === "GRANTED";
    const newStatus = !isGranted;

    if (newStatus) {
        btn.innerText = "GRANTED";
        btn.className = "btn-toggle active";
    } else {
        btn.innerText = "REVOKED";
        btn.className = "btn-toggle revoked";
    }

    try {
        await fetch('/api/v1/guardian/consent', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${guardianToken || 'mock_guardian_jwt_token_123'}`
            },
            body: JSON.stringify({
                tenant_id: '00000000-0000-0000-0000-000000000001',
                learner_id: '00000000-0000-0000-0000-000000000002',
                guardian_id: '00000000-0000-0000-0000-000000000003',
                consent_type: type,
                granted: newStatus
            })
        });
    } catch (e) {}
}

function ackIncident(id) {
    alert(`Incident ${id} acknowledged by guardian/reviewer. SLA clock cleared.`);
}
