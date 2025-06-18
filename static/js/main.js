// Main JavaScript utilities
class EmailUI {
    constructor() {
        // Remove localStorage usage - authentication handled by HttpOnly cookies
        this.currentPage = 1;
        this.pageSize = 20;
        this.sortBy = 'arrival_time';
        this.sortOrder = 'DESC';
        this.searchQuery = '';
    }

    // Authentication helpers
    isAuthenticated() {
        // Authentication is now handled server-side via HttpOnly cookies
        // This method is kept for backward compatibility but not actively used
        return true; // Assume authenticated if page loads
    }

    logout() {
        fetch('/logout', { 
            method: 'POST',
            credentials: 'same-origin'
        })
        .then(() => {
            // Clear any remaining localStorage data (for backward compatibility)
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            window.location.href = '/login';
        });
    }

    // API helpers
    async apiCall(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'  // Include HttpOnly cookies
        };

        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }

        return response;
    }

    // Utility functions
    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));

        if (days === 0) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else if (days === 1) {
            return 'Yesterday';
        } else if (days < 7) {
            return date.toLocaleDateString([], { weekday: 'short' });
        } else {
            return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
        }
    }

    truncateText(text, maxLength = 100) {
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    }

    showAlert(message, type = 'error') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type}`;
        alertDiv.textContent = message;
        
        const container = document.querySelector('.container') || document.body;
        container.insertBefore(alertDiv, container.firstChild);
        
        setTimeout(() => {
            alertDiv.remove();
        }, 5000);
    }

    showLoading(element) {
        element.innerHTML = '<div class="loading"><div class="spinner"></div><p>Loading...</p></div>';
    }
}

// Initialize global instance
window.emailUI = new EmailUI();
