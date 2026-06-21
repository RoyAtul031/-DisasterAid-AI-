// DisasterAid AI Application Controller

document.addEventListener('DOMContentLoaded', () => {
    // Session and state variables
    let sessionId = localStorage.getItem('disasteraid_session_id');
    if (!sessionId) {
        sessionId = 'session_' + Math.random().toString(36).substring(2, 15);
        localStorage.setItem('disasteraid_session_id', sessionId);
    }

    let currentLocation = localStorage.getItem('disasteraid_location') || 'West Bengal, India';
    let currentContacts = null;
    let recognition = null;
    let isRecording = false;

    // DOM Elements
    const chatForm = document.getElementById('chatForm');
    const userInput = document.getElementById('userInput');
    const chatLog = document.getElementById('chatLog');
    const typingIndicator = document.getElementById('typingIndicator');
    const severityPanel = document.getElementById('severityPanel');
    const severityValue = document.getElementById('severityValue');
    const severityIcon = document.getElementById('severityIcon');
    const currentLocationText = document.getElementById('currentLocationText');
    const btnDetectLocation = document.getElementById('btnDetectLocation');
    const btnEditLocation = document.getElementById('btnEditLocation');
    const networkStatus = document.getElementById('networkStatus');
    const networkStatusDot = document.querySelector('.status-dot');
    
    // Contacts and Tabs
    const tabNational = document.getElementById('tabNational');
    const tabState = document.getElementById('tabState');
    const contactsContainer = document.getElementById('contactsContainer');
    let activeContactTab = 'national'; // national or state

    // Location Modal Elements
    const locationModal = document.getElementById('locationModal');
    const modalLocationInput = document.getElementById('modalLocationInput');
    const btnSaveLocation = document.getElementById('btnSaveLocation');
    const btnCancelLocation = document.getElementById('btnCancelLocation');

    // Voice Input setup
    const btnVoiceInput = document.getElementById('btnVoiceInput');

    // Update location context text initially
    currentLocationText.textContent = currentLocation;

    // Initialize Network Status
    function updateOnlineStatus() {
        if (navigator.onLine) {
            networkStatus.textContent = 'Online';
            networkStatusDot.className = 'status-dot online';
        } else {
            networkStatus.textContent = 'Offline';
            networkStatusDot.className = 'status-dot offline';
        }
    }
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus();

    // ────────────────────────────────────────────────────────────────────────
    // 1. Markdown formatter for emergency responses
    // ────────────────────────────────────────────────────────────────────────
    function formatMarkdown(text) {
        if (!text) return '';
        
        let html = text;
        
        // Escape HTML entities to prevent XSS (but preserve our formatting tags we add later)
        html = html
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Replace custom system dividers
        html = html.replace(/(?:───+|━━━+|━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━|─────────────────────────────────────────)/g, '<hr class="emergency-divider">');

        // Headers
        html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.*?)$/gm, '<h3>$1</h3>');
        html = html.replace(/^# (.*?)$/gm, '<h2>$1</h2>');

        // Bold
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // Lists (bullet points, asterisks, emojis)
        html = html.replace(/^\s*[•*]\s*(.*?)$/gm, '<li>$1</li>');
        html = html.replace(/^(✅|🏥|🏠|🍱|⚠️|🚫|📞|🆘|🚑|🏛️|🚒|👮|👧)\s*(.*?)$/gm, '<li>$1 $2</li>');
        
        // Group consecutive list items into ul
        // A simple regex approach to find <li> lines and wrap them
        html = html.replace(/(<li>.*?<\/li>\n?)+/gs, (match) => {
            return '<ul class="emergency-list">' + match + '</ul>';
        });

        // Convert double newlines to paragraphs (excluding list/header wrappers)
        html = html.replace(/\n\n/g, '<br><br>');
        
        // Make phone numbers clickable: match format like 112, 108, 1078 or 10-digit Indian numbers
        // and wrap them in tel: links
        const phoneRegex = /\b(112|108|1078|101|100|1091|1098)\b/g;
        html = html.replace(phoneRegex, '<a href="tel:$1" class="phone-link">$1</a>');

        return html;
    }

    // ────────────────────────────────────────────────────────────────────────
    // 2. Chat Log UI Helpers
    // ────────────────────────────────────────────────────────────────────────
    function addMessageToLog(role, contentText) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.textContent = role === 'user' ? '👤' : '🤖';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (role === 'assistant') {
            contentDiv.innerHTML = formatMarkdown(contentText);
        } else {
            contentDiv.textContent = contentText;
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        chatLog.appendChild(messageDiv);
        
        // Auto-scroll chat log
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    // Update Severity Banner
    function updateSeverityIndicator(severity) {
        if (!severity) {
            severityPanel.className = 'severity-panel hidden';
            return;
        }
        
        severityPanel.className = `severity-panel ${severity.toLowerCase()}`;
        severityValue.textContent = severity;
        
        // Pick severity icon
        if (severity === 'CRITICAL') {
            severityIcon.textContent = '🚨';
            severityValue.className = 'severity-value critical';
            document.getElementById('emergencyBar').style.display = 'block'; // Ensure emergency bar is visible
        } else if (severity === 'HIGH') {
            severityIcon.textContent = '⚠️';
            severityValue.className = 'severity-value high';
        } else if (severity === 'MODERATE') {
            severityIcon.textContent = '⚡';
            severityValue.className = 'severity-value moderate';
        } else {
            severityIcon.textContent = 'ℹ️';
            severityValue.className = 'severity-value advisory';
        }
    }

    // ────────────────────────────────────────────────────────────────────────
    // 3. Emergency Contacts Fetch & Render
    // ────────────────────────────────────────────────────────────────────────
    async function loadContacts(location) {
        try {
            // Try fetching from API
            let data;
            if (navigator.onLine) {
                data = await getEmergencyContacts(location);
                // Save to offline storage
                localStorage.setItem(`contacts_${location}`, JSON.stringify(data));
                localStorage.setItem('last_successful_contacts', JSON.stringify(data));
            } else {
                // Read from local storage cache
                const cachedData = localStorage.getItem(`contacts_${location}`) || localStorage.getItem('last_successful_contacts');
                if (cachedData) {
                    data = JSON.parse(cachedData);
                } else {
                    // Static minimal fallback if nothing is cached
                    data = {
                        location: "Offline Mode",
                        national_contacts: {
                            "National Emergency": "112",
                            "Ambulance": "108",
                            "NDMA Helpline": "1078",
                            "Fire Service": "101"
                        },
                        state_contacts: {}
                    };
                }
            }

            currentContacts = data;
            renderContacts();
        } catch (err) {
            console.error('Failed to load emergency contacts:', err);
            contactsContainer.innerHTML = '<div class="contacts-empty">Failed to load helplines. Call 112 directly.</div>';
        }
    }

    function renderContacts() {
        if (!currentContacts) return;
        contactsContainer.innerHTML = '';
        
        const contactList = activeContactTab === 'national' 
            ? currentContacts.national_contacts 
            : currentContacts.state_contacts;

        const keys = Object.keys(contactList || {});
        if (keys.length === 0) {
            contactsContainer.innerHTML = `<div class="contacts-empty">No specific numbers found for this location. Call 112 or 1078.</div>`;
            return;
        }

        keys.forEach(name => {
            const num = contactList[name];
            const itemDiv = document.createElement('div');
            itemDiv.className = 'contact-item';
            
            itemDiv.innerHTML = `
                <div class="contact-info">
                    <span class="contact-name">${name}</span>
                    <span class="contact-desc">${activeContactTab === 'national' ? 'National Directory' : 'State / Local Helpline'}</span>
                </div>
                <a href="tel:${num}" class="contact-action-btn">${num}</a>
            `;
            contactsContainer.appendChild(itemDiv);
        });
    }

    // Contacts Tab event listeners
    tabNational.addEventListener('click', () => {
        activeContactTab = 'national';
        tabNational.classList.add('active');
        tabState.classList.remove('active');
        renderContacts();
    });

    tabState.addEventListener('click', () => {
        activeContactTab = 'state';
        tabState.classList.add('active');
        tabNational.classList.remove('active');
        renderContacts();
    });

    // ────────────────────────────────────────────────────────────────────────
    // 4. Location Context Management (GPS & Manual)
    // ────────────────────────────────────────────────────────────────────────
    async function updateLocationContext(newLocation) {
        currentLocation = newLocation;
        localStorage.setItem('disasteraid_location', newLocation);
        currentLocationText.textContent = newLocation;
        
        // Sync context to backend if possible
        if (navigator.onLine) {
            try {
                await updateSessionLocation(sessionId, newLocation);
            } catch (e) {
                console.warn("Failed to sync location to server session:", e);
            }
        }
        
        // Reload contacts for new location
        await loadContacts(newLocation);
    }

    // Reverse Geocoding with OSM Nominatim API
    async function reverseGeocode(lat, lon) {
        try {
            const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=10&addressdetails=1`;
            const response = await fetch(url, {
                headers: {
                    'Accept-Language': 'en'
                }
            });
            if (!response.ok) throw new Error('OSM Reverse Geocoding failed');
            
            const data = await response.json();
            const addr = data.address || {};
            
            // Gather state, district, or city
            const state = addr.state || '';
            const district = addr.county || addr.state_district || addr.city_district || '';
            const city = addr.city || addr.town || addr.village || '';
            
            let nameParts = [];
            if (city) nameParts.push(city);
            else if (district) nameParts.push(district);
            
            if (state) nameParts.push(state);
            else nameParts.push("India");
            
            return nameParts.join(", ");
        } catch (e) {
            console.error('Reverse Geocoding error:', e);
            return `Coords: ${lat.toFixed(4)}, ${lon.toFixed(4)}`;
        }
    }

    // Detect location handler
    btnDetectLocation.addEventListener('click', () => {
        if (!navigator.geolocation) {
            alert('Geolocation is not supported by your browser.');
            return;
        }

        currentLocationText.textContent = 'Detecting GPS location...';
        
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;
                
                // Get human readable location text
                const locationText = await reverseGeocode(lat, lon);
                await updateLocationContext(locationText);
            },
            (error) => {
                console.error('GPS positioning failed:', error);
                alert('Could not auto-detect location. Please enter it manually.');
                currentLocationText.textContent = currentLocation;
            },
            { enableHighAccuracy: true, timeout: 8000 }
        );
    });

    // Edit location manual handlers
    btnEditLocation.addEventListener('click', () => {
        modalLocationInput.value = currentLocation;
        locationModal.classList.remove('hidden');
    });

    btnCancelLocation.addEventListener('click', () => {
        locationModal.classList.add('hidden');
    });

    btnSaveLocation.addEventListener('click', async () => {
        const text = modalLocationInput.value.trim();
        if (text) {
            locationModal.classList.add('hidden');
            await updateLocationContext(text);
        }
    });

    // Close modal on escape key
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            locationModal.classList.add('hidden');
        }
    });

    // ────────────────────────────────────────────────────────────────────────
    // 5. Voice Input (Web Speech API)
    // ────────────────────────────────────────────────────────────────────────
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        
        // Try auto-detecting user input language dialects
        recognition.lang = 'en-IN'; // Default to Indian English, covers Hindi/Bengali phonetics reasonably
        
        recognition.onstart = () => {
            isRecording = true;
            btnVoiceInput.classList.add('recording');
            userInput.placeholder = "Listening... Speak clearly.";
        };
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            userInput.value = transcript;
        };
        
        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            alert(`Voice input error: ${event.error}. Please type your message.`);
        };
        
        recognition.onend = () => {
            isRecording = false;
            btnVoiceInput.classList.remove('recording');
            userInput.placeholder = "Describe your situation or request help...";
        };
    } else {
        // Hide/disable mic button if browser doesn't support Web Speech API
        btnVoiceInput.style.display = 'none';
        console.info('Speech recognition not supported in this browser.');
    }

    btnVoiceInput.addEventListener('click', () => {
        if (!recognition) return;
        
        if (isRecording) {
            recognition.stop();
        } else {
            userInput.value = '';
            recognition.start();
        }
    });

    // ────────────────────────────────────────────────────────────────────────
    // 6. Form Submission and Suggestions
    // ────────────────────────────────────────────────────────────────────────
    async function handleFormSubmit(text) {
        if (!text.trim()) return;
        
        // Print user message bubble
        addMessageToLog('user', text);
        userInput.value = '';
        
        // Show typing animation
        typingIndicator.classList.remove('hidden');
        chatLog.scrollTop = chatLog.scrollHeight;
        
        try {
            // Call API
            const result = await sendChatMessage(text, sessionId, currentLocation);
            
            // Hide typing indicator
            typingIndicator.classList.add('hidden');
            
            // Render severity
            updateSeverityIndicator(result.severity);
            
            // Render agent response bubble
            addMessageToLog('assistant', result.response);
        } catch (err) {
            typingIndicator.classList.add('hidden');
            addMessageToLog('assistant', `⚠️ **Coordinator Error:** ${err.message || 'Connection lost. Please call 112 immediately.'}`);
        }
    }

    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        handleFormSubmit(text);
    });

    // Quick suggestion chip listeners
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            handleFormSubmit(chip.textContent);
        });
    });

    // ────────────────────────────────────────────────────────────────────────
    // 7. Load History & Initial Contacts on Start
    // ────────────────────────────────────────────────────────────────────────
    async function loadSessionHistory() {
        if (!navigator.onLine) return; // Skip loading history if offline to avoid error alerts
        
        try {
            const data = await getChatHistory(sessionId);
            if (data && data.history && data.history.length > 0) {
                // Clear initial welcome message if there is actual history
                chatLog.innerHTML = '';
                
                data.history.forEach(msg => {
                    addMessageToLog(msg.role, msg.content);
                    if (msg.role === 'assistant' && msg.severity) {
                        updateSeverityIndicator(msg.severity);
                    }
                });
            }
        } catch (e) {
            console.warn('Failed to load session history:', e);
        }
    }

    // Start everything up
    loadLocationAndContacts();
    
    async function loadLocationAndContacts() {
        // Load initial contacts
        await loadContacts(currentLocation);
        // Load chat history
        await loadSessionHistory();
    }
});
