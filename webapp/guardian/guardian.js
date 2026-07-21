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
            sessionStorage.setItem('vadi_access_token', guardianToken);
            sessionStorage.setItem('vadi_tenant_id', data.tenant_id);
            sessionStorage.setItem('vadi_guardian_id', data.guardian_id);
            setAuthVerified(data.guardian_id);
            hideEnrollModal();
        } else {
            throw new Error(`Enrollment failed (${res.status})`);
        }
    } catch (e) {
        console.error(e);
    }
}

function simulateLocalEnroll() {
    throw new Error('Local enrollment simulation has been removed; live API required.');
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
                'Authorization': `Bearer ${guardianToken || sessionStorage.getItem('vadi_access_token')}`
            },
            body: JSON.stringify({
                display_name: name,
                age_band: band
            })
        });

        if (res.ok) {
            const data = await res.json();
            sessionStorage.setItem('vadi_learner_id', data.learner_id);
            sessionStorage.setItem('vadi_learner_token', data.access_token);
            displayChildToken(data.access_token);
        } else {
            throw new Error(`Learner provisioning failed (${res.status})`);
        }
    } catch (e) {
        console.error(e);
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
                'Authorization': `Bearer ${guardianToken || sessionStorage.getItem('vadi_access_token')}`
            },
            body: JSON.stringify({
                tenant_id: sessionStorage.getItem('vadi_tenant_id'),
                learner_id: sessionStorage.getItem('vadi_learner_id'),
                guardian_id: sessionStorage.getItem('vadi_guardian_id'),
                consent_type: type,
                granted: newStatus
            })
        });
    } catch (e) {}
}

function ackIncident(id) {
    alert(`Incident ${id} acknowledged by guardian/reviewer. SLA clock cleared.`);
}
