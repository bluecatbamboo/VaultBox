// Email Detail Page JavaScript

let currentEmail = null;

document.addEventListener('DOMContentLoaded', function() {
    loadEmail();
});

async function loadEmail() {
    try {
        const emailId = getEmailIdFromUrl();
        
        if (!emailId) {
            showError('Invalid email ID');
            return;
        }

        const response = await fetch(`/api/emails/${emailId}`, {
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'  // Include HttpOnly cookies
        });

        if (response.status === 401) {
            window.location.href = '/login';
            return;
        }

        if (response.ok) {
            currentEmail = await response.json();
            displayEmail(currentEmail);
            updateReadButton();
        } else {
            throw new Error('Failed to load email');
        }
    } catch (error) {
        console.error('Error loading email:', error);
        showError('Error loading email. Please try again.');
    }
}

function getEmailIdFromUrl() {
    const pathParts = window.location.pathname.split('/');
    return pathParts[pathParts.length - 1];
}

function displayEmail(email) {
    const tags = email.tags && email.tags.length > 0 ? 
        `<div class="tags">${email.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}</div>` : '';

    document.getElementById('emailContent').innerHTML = `
        <div class="email-detail">
            <div class="email-header">
                <div class="email-meta">
                    <div class="meta-row">
                        <div class="meta-label">From:</div>
                        <div class="meta-value">${escapeHtml(email.sender)}</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">To:</div>
                        <div class="meta-value">${escapeHtml(email.recipient)}</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">Date:</div>
                        <div class="meta-value">${formatFullDate(email.arrival_time)}</div>
                    </div>
                    <div class="meta-row">
                        <div class="meta-label">Size:</div>
                        <div class="meta-value">${formatBytes(email.size_bytes || 0)}</div>
                    </div>
                </div>
                <h2 class="email-subject">${escapeHtml(email.subject || '(No Subject)')}</h2>
                ${tags}
            </div>
            <div class="email-body"></div>
        </div>
    `;

    // Render the email body
    const bodyContainer = document.querySelector('.email-body');
    function decodeHtmlEntities(str) {
        const txt = document.createElement('textarea');
        txt.innerHTML = str;
        return txt.value;
    }
    let bodyRaw = email.body || '';
    // Try to detect if the body is double-encoded (contains &lt;html&gt;)
    if (/&lt;\s*html[\s&gt;]/i.test(bodyRaw) || /&lt;\s*body[\s&gt;]/i.test(bodyRaw)) {
        bodyRaw = decodeHtmlEntities(bodyRaw);
    }
    if (/<\s*html[\s>]/i.test(bodyRaw) || /<\s*body[\s>]/i.test(bodyRaw) || /<\s*div[\s>]/i.test(bodyRaw)) {
        // Parse the HTML string, strip <html>/<body>/<div> if present, and append nodes
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = bodyRaw;
        let nodesToAppend = [];
        if (tempDiv.children.length === 1 &&
            (['html','body','div'].includes(tempDiv.firstElementChild.tagName.toLowerCase()))) {
            const mainNode = tempDiv.firstElementChild;
            if (mainNode.tagName.toLowerCase() === 'html' && mainNode.children.length === 1 && ['body','div'].includes(mainNode.firstElementChild.tagName.toLowerCase())) {
                nodesToAppend = Array.from(mainNode.firstElementChild.childNodes);
            } else {
                nodesToAppend = Array.from(mainNode.childNodes);
            }
        } else {
            nodesToAppend = Array.from(tempDiv.childNodes);
        }
        nodesToAppend.forEach(node => bodyContainer.appendChild(node.cloneNode(true)));
    } else {
        const pre = document.createElement('pre');
        pre.className = 'email-plain-body';
        pre.textContent = email.body || 'No content';
        bodyContainer.appendChild(pre);
    }

    // Mark as read if it's unread
    if (!email.is_read) {
        markAsRead(false);
    }
}

function updateReadButton() {
    const readBtn = document.getElementById('readBtn');
    if (currentEmail) {
        readBtn.textContent = currentEmail.is_read ? 'Mark as Unread' : 'Mark as Read';
    }
}

async function markAsRead(showNotification = true) {
    if (!currentEmail) return;

    const emailId = getEmailIdFromUrl();
    const newReadStatus = !currentEmail.is_read;

    try {
        const response = await fetch(`/api/emails/${emailId}/read?read=${newReadStatus}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'  // Include HttpOnly cookies
        });

        if (response.ok) {
            currentEmail.is_read = newReadStatus;
            updateReadButton();
            if (showNotification) {
                // Could add a toast notification here
            }
        } else {
            throw new Error('Failed to update read status');
        }
    } catch (error) {
        console.error('Error updating read status:', error);
        if (showNotification) {
            alert('Error updating read status. Please try again.');
        }
    }
}

async function deleteEmail() {
    if (!currentEmail) return;

    if (!confirm('Are you sure you want to delete this email?')) return;

    const emailId = getEmailIdFromUrl();

    try {
        const response = await fetch(`/api/emails/${emailId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin'  // Include HttpOnly cookies
        });

        if (response.ok) {
            goBack();
        } else {
            throw new Error('Failed to delete email');
        }
    } catch (error) {
        console.error('Error deleting email:', error);
        alert('Error deleting email. Please try again.');
    }
}

function goBack() {
    window.location.href = '/mailbox';
}

function logout() {
    fetch('/logout', { 
        method: 'POST',
        credentials: 'same-origin'  // Include HttpOnly cookies
    })
        .then(() => {
            // Clear any remaining localStorage data (for backward compatibility)
            localStorage.removeItem('authToken');
            localStorage.removeItem('username');
            window.location.href = '/login';
        });
}

function showError(message) {
    document.getElementById('emailContent').innerHTML = 
        `<div class="error">${message}</div>`;
}

// Utility Functions
function formatFullDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString([], {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
