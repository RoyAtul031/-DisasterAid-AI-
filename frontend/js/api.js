// DisasterAid AI API Service Client

const BASE_URL = window.location.origin;

/**
 * Sends a message to the DisasterAid multi-agent system.
 * @param {string} message - User input description.
 * @param {string|null} sessionId - Current chat session ID.
 * @param {string|null} location - Geolocation context.
 * @returns {Promise<object>} Response containing response text, severity, and session_id.
 */
async function sendChatMessage(message, sessionId = null, location = null) {
    const response = await fetch(`${BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            message,
            session_id: sessionId,
            location
        })
    });
    
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to communicate with emergency coordinator.');
    }
    
    return await response.json();
}

/**
 * Updates the current session location on the server.
 * @param {string} sessionId 
 * @param {string} location 
 * @returns {Promise<object>}
 */
async function updateSessionLocation(sessionId, location) {
    const response = await fetch(`${BASE_URL}/api/location`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            session_id: sessionId,
            location
        })
    });
    
    if (!response.ok) {
        throw new Error('Failed to update location context on server.');
    }
    
    return await response.json();
}

/**
 * Retrieves the chat history for a session.
 * @param {string} sessionId 
 * @returns {Promise<object>}
 */
async function getChatHistory(sessionId) {
    const response = await fetch(`${BASE_URL}/api/history?session_id=${encodeURIComponent(sessionId)}`);
    if (!response.ok) {
        throw new Error('Failed to retrieve chat history.');
    }
    return await response.json();
}

/**
 * Retrieves verified emergency contacts for a location.
 * @param {string} location 
 * @returns {Promise<object>}
 */
async function getEmergencyContacts(location) {
    const response = await fetch(`${BASE_URL}/api/contacts?location=${encodeURIComponent(location)}`);
    if (!response.ok) {
        throw new Error('Failed to retrieve verified contacts.');
    }
    return await response.json();
}
