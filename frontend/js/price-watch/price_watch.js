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


async function searchFlights(flightRequestData) {
    const response = await fetch(`${API_BASE_URL}/search/flights`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(flightRequestData)
    });
    if (!response.ok) throw new Error("Flight search service failed to fetch results.");
    return await response.json();
}

/**
 * Sends a search request payload to the backend to get real-time hotel lists.
 */
async function searchHotels(hotelRequestData) {
    const response = await fetch(`${API_BASE_URL}/search/hotels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(hotelRequestData)
    });
    if (!response.ok) throw new Error("Hotel search service failed to fetch results.");
    return await response.json();
}



function renderFlightSearchResults(flightsArray, searchContext) {
    const resultsContainer = document.getElementById("flight-results-display");
    if (!resultsContainer) return;

    if (!flightsArray || flightsArray.length === 0) {
        resultsContainer.innerHTML = `<p class="text-muted">No flights matched your specified filters.</p>`;
        return;
    }

    resultsContainer.innerHTML = flightsArray.map((flight, index) => {
        // Clean numeric sanitizer for setup handling
        const numericPrice = parseFloat(flight.price.replace(/[^0-9.]/g, '')) || 0;

        return `
            <div class="card mb-3 shadow-sm border-start border-info border-4" id="search-flight-row-${index}">
                <div class="card-body d-flex justify-content-between align-items-center">
                    <div class="d-flex align-items-center gap-3">
                        <img src="${flight.airline_logo}" alt="${flight.airline}" style="width: 45px; height: 45px; object-fit: contain;" class="rounded border p-1 bg-light">
                        <div>
                            <h6 class="mb-1">${flight.airline} <span class="badge bg-light text-dark small">${flight.travel_class}</span></h6>
                            <p class="mb-1 small text-dark">
                                <strong>${flight.departure_time}</strong> (${searchContext.origin}) → 
                                <strong>${flight.arrival_time}</strong> (${searchContext.destination})
                            </p>
                            <small class="text-muted d-block">${flight.duration} | ${flight.stops}</small>
                        </div>
                    </div>
                    
                    <div class="d-flex align-items-center gap-4">
                        <div class="text-end">
                            <span class="fs-5 fw-bold text-success">INR ${numericPrice}</span>
                        </div>
                        
                        <!-- Notification Track Bell Action Trigger -->
                        <div class="search-bell-action-wrapper" 
                             style="cursor: pointer; position: relative;" 
                             title="Click to track prices for this flight route"
                             onclick="handleTrackFromSearchResult('${searchContext.origin}', '${searchContext.destination}', '${searchContext.departure_date}', ${numericPrice}, this)">
                            <span class="bell-icon" style="font-size: 1.6rem; filter: grayscale(100%); transition: all 0.25s ease;">🔔</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Iterates through a live hotels dataset array and builds accommodation display blocks.
 */
function renderHotelSearchResults(hotelsArray, searchContext) {
    const resultsContainer = document.getElementById("hotel-results-display");
    if (!resultsContainer) return;

    if (!hotelsArray || hotelsArray.length === 0) {
        resultsContainer.innerHTML = `<p class="text-muted">No hotel inventories found for this area location.</p>`;
        return;
    }

    resultsContainer.innerHTML = hotelsArray.map((hotel, index) => {
        const numericPrice = parseFloat(hotel.price) || 0;

        return `
            <div class="card mb-3 shadow-sm" id="search-hotel-row-${index}">
                <div class="row g-0">
                    <div class="col-md-4">
                        <img src="${hotel.image}" class="img-fluid rounded-start h-100 w-100" style="object-fit: cover; max-height: 180px;" alt="${hotel.name}">
                    </div>
                    <div class="col-md-8">
                        <div class="card-body h-100 d-flex flex-column justify-content-between">
                            <div>
                                <div class="d-flex justify-content-between align-items-start">
                                    <h5 class="card-title mb-1">${hotel.name}</h5>
                                    <span class="badge bg-warning text-dark">⭐ ${hotel.rating}</span>
                                </div>
                                <p class="card-text small text-secondary mb-2">${hotel.location}</p>
                            </div>
                            
                            <div class="d-flex justify-content-between align-items-center mt-3">
                                <div>
                                    <span class="fs-4 fw-bold text-success">INR ${numericPrice}</span>
                                    <small class="text-muted d-block" style="font-size: 0.75rem;">per night</small>
                                </div>
                                
                                <!-- Notification Track Bell Action Trigger -->
                                <div class="search-bell-action-wrapper" 
                                     style="cursor: pointer;" 
                                     title="Track price drops for this hotel stay"
                                     onclick="handleTrackFromSearchResult('${searchContext.location}', '${hotel.name}', '${searchContext.check_in}', ${numericPrice}, this)">
                                    <span class="bell-icon" style="font-size: 1.6rem; filter: grayscale(100%); transition: all 0.25s ease;">🔔</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Handles converting a click event on an inventory bell icon into an active database Price Watch tracker rule.
 */
async function handleTrackFromSearchResult(origin, destination, travelDate, currentPrice, bellElement) {
    // Current authenticated traveler context definition mapping placeholder
    const activeUserId = 1; 

    // Setup configuration object matching backend validation expectations
    const trackPayload = {
        user_id: activeUserId,
        origin: origin.toUpperCase().trim(),
        destination: destination.trim(),
        travel_date: travelDate,
        initial_price: currentPrice,
        current_price: currentPrice,
        currency: "INR",
        is_active: true,
        // Set up an automatic trigger drop alert threshold condition at a 10% reduction default strategy
        trigger_percent_drop: 10 
    };

    try {
        // Run API service validation route call execution step
        await CreatePriceWatch(trackPayload);
        
        // Transform the bell icon styling inside the UI layout to highlight successful registration
        const icon = bellElement.querySelector('.bell-icon');
        if (icon) {
            icon.style.filter = "none"; // Remove grayscale filter, unlocking glowing yellow status color
            icon.animate([
                { transform: 'rotate(0deg)' },
                { transform: 'rotate(15deg)' },
                { transform: 'rotate(-15deg)' },
                { transform: 'rotate(0deg)' }
            ], { duration: 400, iterations: 1 });
        }
        
        bellElement.style.pointerEvents = "none"; // Disable tracking multiple copies by accident
        bellElement.setAttribute("title", "Currently active tracking subscription");
        
        // Refresh active listings tracking component panels cleanly if accessible on layout screen context
        if (typeof renderWatchesUI === "function") {
            renderWatchesUI(activeUserId);
        }

    } catch (error) {
        console.error("Failed to map tracker from search node item click context:", error);
        alert(`Could not configure automatic tracking: ${error.message}`);
    }
}

