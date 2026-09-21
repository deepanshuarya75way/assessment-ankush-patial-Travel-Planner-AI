/**
 * /frontend/js/price-watch/price-watch.js
 * Frontend controller for managing travel price watches and triggered alerts dashboard.
 */

const API_BASE_URL = "http://127.0.0.1:8000"; 

document.addEventListener("DOMContentLoaded", () => {
    // Replace with your real authenticated user session context
    const currentUserId = 1; 

    initPriceWatchDashboard(currentUserId);
});

async function CreatePriceWatch(watchData) {
    const response = await fetch(`${API_BASE_URL}/price-watches/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(watchData)
    });
    if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Validation engine failure handling payload.");
    }
    return await response.json();
}


async function getPriceWatches(userId, activeOnly = true) {
    const response = await fetch(`${API_BASE_URL}/price-watches/user/${userId}?active_only=${activeOnly}`);
    if (!response.ok) throw new Error("Failed to load tracking data contextual results.");
    return await response.json();
}

/**
 * Custom patch update to disable a watch tracking rule (Soft Delete / Turn Off).
 */
async function UpdatPriceWatch(watchId) {
    const response = await fetch(`${API_BASE_URL}/price-watches/${watchId}/deactivate`, {
        method: "PATCH"
    });
    if (!response.ok) throw new Error("Could not modify active tracking rule status settings.");
    return await response.json();
}

/**
 * Permanently drops an alert log index record completely out of dashboard view storage.
 */
async function DeletePriceWatch(alertId) {
    const response = await fetch(`${API_BASE_URL}/alerts/${alertId}`, {
        method: "DELETE"
    });
    if (!response.ok) throw new Error("Entity destruction execution operation failure.");
    return true; 
}

/**
 * Pulls down historical notification banner data alerts dashboard collection logs.
 */
async function getPriceAlerts(userId) {
    const response = await fetch(`${API_BASE_URL}/alerts/user/${userId}`);
    if (!response.ok) throw new Error("Failed to load historical trigger states.");
    return await response.json();
}

/**
 * Changes read status visibility toggles for an individual message item row.
 */
async function MarkAlertsAsRead(alertId) {
    const response = await fetch(`${API_BASE_URL}/alerts/${alertId}/read`, {
        method: "PATCH"
    });
    if (!response.ok) throw new Error("Database transaction change reject response.");
    return await response.json();
}


// =========================================================================
// 2. DOM INTERACTION & LAYOUT RENDERING INTERFACE LOGIC
// =========================================================================

function initPriceWatchDashboard(userId) {
    renderWatchesUI(userId);
    renderAlertsUI(userId);

    const watchForm = document.getElementById("create-watch-form");
    if (watchForm) {
        watchForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            
            const formData = {
                user_id: userId,
                origin: document.getElementById("watch-origin").value.toUpperCase().trim(),
                destination: document.getElementById("watch-destination").value.toUpperCase().trim(),
                travel_date: document.getElementById("watch-date").value,
                initial_price: parseFloat(document.getElementById("watch-current-price").value),
                current_price: parseFloat(document.getElementById("watch-current-price").value),
                currency: document.getElementById("watch-currency").value || "INR",
                is_active: true
            };

            const targetPriceInput = document.getElementById("watch-target-price").value;
            const percentDropInput = document.getElementById("watch-percent-drop").value;

            if (targetPriceInput) formData.target_price = parseFloat(targetPriceInput);
            if (percentDropInput) formData.trigger_percent_drop = parseInt(percentDropInput);

            try {
                await CreatePriceWatch(formData);
                alert("Success! Your price watch tracker has been successfully configured.");
                e.target.reset();
                renderWatchesUI(userId); // Live refresh
            } catch (error) {
                console.error(error);
                alert(`Could not set up tracker: ${error.message}`);
            }
        });
    }
}

async function renderWatchesUI(userId) {
    const listContainer = document.getElementById("price-watches-list");
    if (!listContainer) return;

    try {
        const watches = await getPriceWatches(userId);
        if (watches.length === 0) {
            listContainer.innerHTML = `<p class="text-muted">You aren't tracking any trip routes currently.</p>`;
            return;
        }

        listContainer.innerHTML = watches.map(watch => `
            <div class="card mb-3 shadow-sm border-start border-primary border-4" id="watch-card-${watch.id}">
                <div class="card-body d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="card-title mb-1">✈️ ${watch.origin} to ${watch.destination}</h5>
                        <p class="card-text text-secondary small mb-0">
                            Travel Date: <strong>${watch.travel_date}</strong> | Base: ${watch.currency} ${watch.initial_price}
                        </p>
                        <div class="mt-2">
                            <span class="badge bg-info text-dark">Current: ${watch.currency} ${watch.current_price}</span>
                            ${watch.target_price ? `<span class="badge bg-warning text-dark">Target: watch.currency {watch.target_price}</span>` : ''}
                        </div>
                    </div>
                    <button class="btn btn-outline-danger btn-sm" onclick="handleDeactivateWatch(${watch.id})">Stop Tracking</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        listContainer.innerHTML = `<div class="alert alert-danger">Error rendering active trackers.</div>`;
    }
}

async function renderAlertsUI(userId) {
    const listContainer = document.getElementById("price-alerts-list");
    if (!listContainer) return;

    try {
        const alerts = await getPriceAlerts(userId);
        if (alerts.length === 0) {
            listContainer.innerHTML = `<p class="text-muted">No pricing notifications generated yet.</p>`;
            return;
        }

        listContainer.innerHTML = alerts.map(alert => `
            <div class="alert ${alert.is_read ? 'alert-light border' : 'alert-warning border-warning'} d-flex justify-content-between align-items-start shadow-sm" id="alert-item-${alert.id}">
                <div>
                    <strong>${alert.title}</strong>
                    <p class="mb-1 text-dark small">${alert.message}</p>
                </div>
                <div class="d-flex flex-column gap-1">
                    ${!alert.is_read ? `<button class="btn btn-sm btn-outline-secondary py-0 px-2" onclick="handleMarkRead(\${alert.id})">Mark Read</button>` : ''}
                    <button class="btn btn-sm text-danger py-0 px-2" onclick="handleDeleteAlert(${alert.id})">Delete</button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        listContainer.innerHTML = `<div class="alert alert-danger">Error rendering message logs.</div>`;
    }
}

// Global button click wrapper handlers
async function handleDeactivateWatch(watchId) {
    if (!confirm("Stop tracking this trip route?")) return;
    try {
        await UpdatPriceWatch(watchId);
        document.getElementById(`watch-card-${watchId}`)?.remove();
    } catch (error) {
        alert("Action update failed.");
    }
}

async function handleMarkRead(alertId) {
    try {
        await MarkAlertsAsRead(alertId);
        const item = document.getElementById(`alert-item-${alertId}`);
        if (item) {
            item.classList.replace('alert-warning', 'alert-light');
            item.classList.remove('border-warning');
            item.querySelector('button[onclick^="handleMarkRead"]')?.remove();
        }
    } catch (error) {
        console.error(error);
    }
}

async function handleDeleteAlert(alertId) {
    if (!confirm("Permanently delete this alert history card entry?")) return;
    try {
        await DeletePriceWatch(alertId);
        document.getElementById(`alert-item-${alertId}`)?.remove();
    } catch (error) {
        alert("Could not remove log entry.");
    }
}
