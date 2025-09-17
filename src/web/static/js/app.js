// WakeUpAI Web UI JavaScript

class WakeUpAIApp {
    constructor() {
        this.feedTypes = [];
        this.alarms = [];
        this.init();
    }

    async init() {
        await this.loadFeedTypes();
        await this.loadAlarms();
        this.setupEventListeners();
        this.startPeriodicRefresh();
    }

    // API Methods
    async apiCall(endpoint, options = {}) {
        try {
            const response = await fetch(endpoint, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    }

    async loadFeedTypes() {
        try {
            const data = await this.apiCall('/api/feed-types');
            this.feedTypes = data.feed_types;
            this.populateFeedTypeSelects();
        } catch (error) {
            this.showMessage('Failed to load feed types', 'error');
        }
    }

    async loadAlarms() {
        try {
            this.alarms = await this.apiCall('/api/alarms');
            this.renderAlarms();
        } catch (error) {
            this.showMessage('Failed to load alarms', 'error');
            document.getElementById('alarms-list').innerHTML = 
                '<div class="empty-state"><i class="fas fa-exclamation-triangle"></i><p>Failed to load alarms</p></div>';
        }
    }

    async createAlarm(alarmData) {
        try {
            const response = await this.apiCall('/api/alarms', {
                method: 'POST',
                body: JSON.stringify(alarmData)
            });
            this.showMessage(response.message, 'success');
            await this.loadAlarms();
            return true;
        } catch (error) {
            this.showMessage(`Failed to create alarm: ${error.message}`, 'error');
            return false;
        }
    }

    async updateAlarm(alarmId, alarmData) {
        try {
            const response = await this.apiCall(`/api/alarms/${alarmId}`, {
                method: 'PUT',
                body: JSON.stringify(alarmData)
            });
            this.showMessage(response.message, 'success');
            await this.loadAlarms();
            return true;
        } catch (error) {
            this.showMessage(`Failed to update alarm: ${error.message}`, 'error');
            return false;
        }
    }

    async deleteAlarm(alarmId) {
        try {
            const response = await this.apiCall(`/api/alarms/${alarmId}`, {
                method: 'DELETE'
            });
            this.showMessage(response.message, 'success');
            await this.loadAlarms();
            return true;
        } catch (error) {
            this.showMessage(`Failed to delete alarm: ${error.message}`, 'error');
            return false;
        }
    }

    async stopAlarm(alarmId) {
        try {
            const response = await this.apiCall(`/api/alarms/${alarmId}/stop`, {
                method: 'POST'
            });
            this.showMessage(response.message, 'success');
            await this.loadAlarms();
            return true;
        } catch (error) {
            this.showMessage(`Failed to stop alarm: ${error.message}`, 'error');
            return false;
        }
    }

    async stopAllAlarms() {
        try {
            const response = await this.apiCall('/api/alarms/stop-all', {
                method: 'POST'
            });
            this.showMessage(response.message, 'success');
            await this.loadAlarms();
            return true;
        } catch (error) {
            this.showMessage(`Failed to stop all alarms: ${error.message}`, 'error');
            return false;
        }
    }

    // UI Methods
    populateFeedTypeSelects() {
        const selects = ['feed-type', 'edit-feed-type'];
        
        selects.forEach(selectId => {
            const select = document.getElementById(selectId);
            if (!select) return;
            
            // Clear existing options except the first one
            while (select.children.length > 1) {
                select.removeChild(select.lastChild);
            }
            
            this.feedTypes.forEach(feedType => {
                const option = document.createElement('option');
                option.value = feedType.id;
                option.textContent = feedType.name;
                option.title = feedType.description;
                select.appendChild(option);
            });
        });
    }

    renderFeedOptions(feedTypeId, containerId, currentOptions = {}) {
        const container = document.getElementById(containerId);
        const parentGroup = container.closest('.form-group');
        
        if (!feedTypeId) {
            parentGroup.style.display = 'none';
            container.innerHTML = '';
            return;
        }

        const feedType = this.feedTypes.find(ft => ft.id === feedTypeId);
        if (!feedType || !feedType.options) {
            parentGroup.style.display = 'none';
            container.innerHTML = '';
            return;
        }

        parentGroup.style.display = 'block';
        container.innerHTML = '';

        Object.entries(feedType.options).forEach(([optionKey, optionConfig]) => {
            const optionDiv = document.createElement('div');
            optionDiv.className = 'feed-option';

            const label = document.createElement('label');
            label.textContent = optionKey.charAt(0).toUpperCase() + optionKey.slice(1);
            optionDiv.appendChild(label);

            let input;
            const currentValue = currentOptions[optionKey] || optionConfig.default || '';

            switch (optionConfig.type) {
                case 'select':
                    input = document.createElement('select');
                    input.name = optionKey;
                    
                    optionConfig.choices.forEach(choice => {
                        const option = document.createElement('option');
                        option.value = choice;
                        option.textContent = choice;
                        option.selected = choice === currentValue;
                        input.appendChild(option);
                    });
                    break;

                case 'textarea':
                    input = document.createElement('textarea');
                    input.name = optionKey;
                    input.placeholder = optionConfig.placeholder || '';
                    input.value = currentValue;
                    break;

                default: // text
                    input = document.createElement('input');
                    input.type = 'text';
                    input.name = optionKey;
                    input.placeholder = optionConfig.placeholder || '';
                    input.value = currentValue;
                    break;
            }

            optionDiv.appendChild(input);
            container.appendChild(optionDiv);
        });
    }

    renderAlarms() {
        const container = document.getElementById('alarms-list');
        const stopAllBtn = document.getElementById('stop-all-btn');
        
        if (this.alarms.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-clock"></i>
                    <p>No alarms configured yet</p>
                    <p>Add your first alarm using the form on the left</p>
                </div>
            `;
            stopAllBtn.style.display = 'none';
            return;
        }

        const hasActiveAlarms = this.alarms.some(alarm => alarm.is_active);
        stopAllBtn.style.display = hasActiveAlarms ? 'block' : 'none';

        container.innerHTML = this.alarms.map(alarm => this.renderAlarmCard(alarm)).join('');
        
        // Add event listeners to the newly created buttons
        this.setupAlarmEventListeners();
    }

    setupAlarmEventListeners() {
        // Add event listeners to edit buttons
        document.querySelectorAll('.btn-edit').forEach(button => {
            button.addEventListener('click', (e) => {
                const alarmId = button.dataset.alarmId;
                this.handleEditAlarmButton(alarmId);
            });
        });

        // Add event listeners to delete buttons
        document.querySelectorAll('.btn-delete').forEach(button => {
            button.addEventListener('click', (e) => {
                const alarmId = button.dataset.alarmId;
                this.handleDeleteAlarm(alarmId);
            });
        });

        // Add event listeners to stop buttons
        document.querySelectorAll('.btn-stop').forEach(button => {
            button.addEventListener('click', (e) => {
                const alarmId = button.dataset.alarmId;
                this.handleStopAlarm(alarmId);
            });
        });
    }

    async handleEditAlarmButton(alarmId) {
        this.openEditModal(alarmId);
    }

    async handleDeleteAlarm(alarmId) {
        if (confirm('Are you sure you want to delete this alarm?')) {
            await this.deleteAlarm(alarmId);
        }
    }

    async handleStopAlarm(alarmId) {
        await this.stopAlarm(alarmId);
    }

    renderAlarmCard(alarm) {
        const feedType = this.feedTypes.find(ft => ft.id === alarm.feed_type);
        const feedTypeName = feedType ? feedType.name : alarm.feed_type;
        
        let statusClass = 'status-disabled';
        let statusIcon = 'fas fa-pause';
        let statusText = 'Disabled';
        
        if (alarm.is_active) {
            statusClass = 'status-active';
            statusIcon = 'fas fa-volume-up';
            statusText = 'Playing';
        } else if (alarm.enabled) {
            statusClass = 'status-enabled';
            statusIcon = 'fas fa-check';
            statusText = 'Enabled';
        }

        const feedOptionsText = Object.keys(alarm.feed_options).length > 0 
            ? Object.entries(alarm.feed_options).map(([key, value]) => `${key}: ${value}`).join(', ')
            : 'Default settings';

        return `
            <div class="alarm-card ${alarm.is_active ? 'active' : ''}" data-alarm-id="${alarm.id}">
                <div class="alarm-header">
                    <div class="alarm-time">${alarm.alarm_time}</div>
                    <div class="alarm-status ${statusClass}">
                        <i class="${statusIcon}"></i>
                        ${statusText}
                    </div>
                </div>
                
                <div class="alarm-name">${alarm.name}</div>
                <div class="alarm-details">
                    <strong>Content:</strong> ${feedTypeName}<br>
                    <strong>Options:</strong> ${feedOptionsText}
                </div>
                
                <div class="alarm-actions">
                    ${alarm.is_active ? 
                        `<button class="btn btn-danger btn-stop" data-alarm-id="${alarm.id}">
                            <i class="fas fa-stop"></i> Stop
                        </button>` : ''
                    }
                    <button class="btn btn-secondary btn-edit" data-alarm-id="${alarm.id}">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                    <button class="btn btn-danger btn-delete" data-alarm-id="${alarm.id}">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </div>
            </div>
        `;
    }

    setupEventListeners() {
        // Add alarm form
        document.getElementById('alarm-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleAddAlarm(e.target);
        });

        // Edit alarm form
        document.getElementById('edit-alarm-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleEditAlarm(e.target);
        });

        // Feed type change handlers
        document.getElementById('feed-type').addEventListener('change', (e) => {
            this.renderFeedOptions(e.target.value, 'feed-options-container');
        });

        document.getElementById('edit-feed-type').addEventListener('change', (e) => {
            this.renderFeedOptions(e.target.value, 'edit-feed-options-container');
        });

        // Stop all alarms button
        document.getElementById('stop-all-btn').addEventListener('click', async () => {
            if (confirm('Are you sure you want to stop all active alarms?')) {
                await this.stopAllAlarms();
            }
        });

        // Modal handlers
        const modal = document.getElementById('edit-modal');
        const closeBtn = modal.querySelector('.close');
        const cancelBtn = document.getElementById('cancel-edit');

        closeBtn.addEventListener('click', () => this.closeModal());
        cancelBtn.addEventListener('click', () => this.closeModal());
        
        window.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal();
            }
        });


    }

    async handleAddAlarm(form) {
        const formData = new FormData(form);
        const alarmData = {
            alarm_time: formData.get('alarm_time'),
            name: formData.get('name'),
            feed_type: formData.get('feed_type'),
            enabled: formData.has('enabled'),
            feed_options: {}
        };

        // Collect feed options
        const optionsContainer = document.getElementById('feed-options-container');
        const optionInputs = optionsContainer.querySelectorAll('input, select, textarea');
        optionInputs.forEach(input => {
            if (input.value) {
                alarmData.feed_options[input.name] = input.value;
            }
        });

        const success = await this.createAlarm(alarmData);
        if (success) {
            form.reset();
            document.getElementById('feed-options').style.display = 'none';
        }
    }

    async handleEditAlarm(form) {
        const formData = new FormData(form);
        const alarmId = document.getElementById('edit-alarm-id').value;
        const alarmData = {
            alarm_time: formData.get('alarm_time'),
            name: formData.get('name'),
            feed_type: formData.get('feed_type'),
            enabled: formData.has('enabled'),
            feed_options: {}
        };

        // Collect feed options
        const optionsContainer = document.getElementById('edit-feed-options-container');
        const optionInputs = optionsContainer.querySelectorAll('input, select, textarea');
        optionInputs.forEach(input => {
            if (input.value) {
                alarmData.feed_options[input.name] = input.value;
            }
        });

        const success = await this.updateAlarm(alarmId, alarmData);
        if (success) {
            this.closeModal();
        }
    }

    openEditModal(alarmId) {
        const alarm = this.alarms.find(a => a.id === alarmId);
        if (!alarm) return;

        const modal = document.getElementById('edit-modal');
        
        // Populate form
        document.getElementById('edit-alarm-id').value = alarm.id;
        document.getElementById('edit-alarm-time').value = alarm.alarm_time;
        document.getElementById('edit-alarm-name').value = alarm.name;
        document.getElementById('edit-feed-type').value = alarm.feed_type;
        document.getElementById('edit-alarm-enabled').checked = alarm.enabled;

        // Render feed options
        this.renderFeedOptions(alarm.feed_type, 'edit-feed-options-container', alarm.feed_options);

        modal.style.display = 'block';
    }

    closeModal() {
        document.getElementById('edit-modal').style.display = 'none';
    }

    showMessage(message, type = 'info') {
        const container = document.getElementById('status-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `status-message ${type}`;
        messageDiv.innerHTML = `
            ${message}
            <button class="close-btn">&times;</button>
        `;

        container.appendChild(messageDiv);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        }, 5000);

        // Manual close button
        messageDiv.querySelector('.close-btn').addEventListener('click', () => {
            if (messageDiv.parentNode) {
                messageDiv.parentNode.removeChild(messageDiv);
            }
        });
    }

    startPeriodicRefresh() {
        // Refresh alarms every 30 seconds to update active status
        setInterval(async () => {
            await this.loadAlarms();
        }, 30000);
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing WakeUpAI app');
    new WakeUpAIApp();
});