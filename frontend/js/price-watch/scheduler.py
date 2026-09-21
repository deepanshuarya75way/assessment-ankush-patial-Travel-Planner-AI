import asyncio
import importlib.util
import sys
from typing import Any


const SCHEDULER_API_BASE_URL = "http://127.0.0.1:8000"; 

document.addEventListener("DOMContentLoaded", () => {
    // Replace with your real authenticated user session context
    const currentUserId = 1; 

    initSchedulerDashboard(currentUserId);
});


async function TriggerDailyDigest(userId) {
    const response = await fetch(`${SCHEDULER_API_BASE_URL}/alerts/user/${userId}/trigger-digest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
    });
    if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Automation execution block failed to trigger digest payload.");
    }
    return await response.json();
}


async function UpdateScraperInterval(userId, intervalMinutes) {
    const response = await fetch(`${SCHEDULER_API_BASE_URL}/scheduler/user/${userId}/scraper-interval`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interval_minutes: intervalMinutes })
    });
    if (!response.ok) throw new Error("Failed to commit automated sync interval updates.");
    return await response.json();
}

function GetSchedulerStatus(userId) {
    const response = await fetch(`${SCHEDULER_API_BASE_URL}/scheduler/user/${userId}/status`);
    if (!response.ok) throw new Error("Failed to load historical automation signal intervals.");
    return await response.json();
}



function initSchedulerDashboard(userId) {
    renderSchedulerUI(userId);

    // 1. Intercept manual digest processing requests
    const digestBtn = document.getElementById("trigger-digest-now-btn");
    if (digestBtn) {
        digestBtn.addEventListener("click", () => handleManualDigestTrigger(userId));
    }

    // 2. Intercept intervals modification choice changes
    const intervalSelect = document.getElementById("scraper-frequency-select");
    if (intervalSelect) {
        intervalSelect.addEventListener("change", (e) => handleScraperIntervalChange(userId, parseInt(e.target.value)));
    }
}

/**
 * Builds analytical text diagnostics showing when upcoming scans will happen.
 */
async function renderSchedulerUI(userId) {
    const statusContainer = document.getElementById("scheduler-status-display");
    if (!statusContainer) return;

    try {
        const statusData = await GetSchedulerStatus(userId);
        
        // Formulate a beautiful status board view context component block
        statusContainer.innerHTML = `
            <div class="card bg-dark text-white p-3 shadow-sm border-0">
                <h6 class="text-info mb-2">⚙️ Automation Status Summary</h6>
                <div class="small">
                    <p class="mb-1">Active Trackers Synced: <strong>${statusData.monitored_watches_count || 0}</strong></p>
                    <p class="mb-1">Active Scraper Cadence: <span class="badge bg-secondary">${statusData.current_interval_minutes || 60} minutes</span></p>
                    <p class="mb-0 text-white-50">Next scheduled crawl: ${statusData.next_run_timestamp ? new Date(statusData.next_run_timestamp).toLocaleString() : 'Pending scheduler ring'}</p>
                </div>
            </div>
        `;
        
        // Sync layout configuration form input properties dynamically based on actual database configurations
        const intervalSelect = document.getElementById("scraper-frequency-select");
        if (intervalSelect && statusData.current_interval_minutes) {
            intervalSelect.value = statusData.current_interval_minutes;
        }

    } catch (error) {
        console.warning("Real runtime scheduler properties absent. Rendering static visualization layout defaults instead.");
        statusContainer.innerHTML = `
            <div class="card border p-3 bg-light">
                <span class="text-muted d-block small mb-1">⏰ Automated Scraper Routine: <strong>Active</strong></span>
                <small class="text-secondary">Trackers scan continuously in the background using automated async processing queues.</small>
            </div>
        `;
    }
}

/**
 * Manages executing a manual dispatch request for compiled summaries.
 */
async function handleManualDigestTrigger(userId) {
    const statusBox = document.getElementById("digest-execution-feedback");
    try {
        if (statusBox) statusBox.innerHTML = `<span class="spinner-border spinner-border-sm text-primary"></span> Processing compilation blocks...`;
        
        const result = await TriggerDailyDigest(userId);
        
        if (statusBox) {
            if (result.status === "skipped") {
                statusBox.innerHTML = `<div class="alert alert-light border mt-2 small text-dark">ℹ️ ${result.detail}</div>`;
            } else {
                statusBox.innerHTML = `<div class="alert alert-success mt-2 small">🎉 ${result.detail}</div>`;
            }
        }
    } catch (error) {
        console.error(error);
        if (statusBox) {
            statusBox.innerHTML = `<div class="alert alert-danger mt-2 small">Error running summary compiler: ${error.message}</div>`;
        }
    }
}

/**
 * Handles modifying background database interval configurations smoothly.
 */
async function handleScraperIntervalChange(userId, intervalMinutes) {
    try {
        await UpdateScraperInterval(userId, intervalMinutes);
        alert(`Success! Scraper task routine timing updated to run every ${intervalMinutes} minutes.`);
        renderSchedulerUI(userId); // Live diagnostics panel refresh
    } catch (error) {
        console.error("Scheduler configuration adjustment reject:", error);
        alert("Failed to modify background scheduler tracking cadence intervals.");
    }
}
