// mailbox.js
let currentPage = 1;
let totalPages = 1;
let currentPageSize = 20;
let searchQuery = '';
let selectedEmails = new Set();

document.addEventListener('DOMContentLoaded', function() {
    // Remove auth check since HttpOnly cookies are handled server-side
    loadEmails();
    
    // Auto-refresh mailbox every 30 seconds
    setInterval(() => {
        // Only refresh if not searching (optional: you can remove this check if you want to always refresh)
        if (!searchQuery) {
            refreshEmails();
        }
    }, 30000);
});

function showNotification(message, type = 'info', duration = 3000) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 4px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        max-width: 400px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        transition: opacity 0.3s ease;
    `;
    
    // Set background color based on type
    switch(type) {
        case 'success': notification.style.backgroundColor = '#4CAF50'; break;
        case 'error': notification.style.backgroundColor = '#f44336'; break;
        case 'warning': notification.style.backgroundColor = '#ff9800'; break;
        case 'info': 
        default: notification.style.backgroundColor = '#2196F3'; break;
    }
    
    // Add to page
    document.body.appendChild(notification);
    
    // Auto-remove after duration
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, duration);
}

async function loadEmails(page = 1) {
    try {
        const params = new URLSearchParams({
            page: page,
            page_size: currentPageSize,
            sort_by: 'arrival_time',
            sort_order: 'DESC'
        });
        if (searchQuery) {
            // If advanced syntax detected, use 'advanced' param
            if (/\b(from|to|subject|body|is_read|date|recent):/i.test(searchQuery)) {
                params.append('advanced', searchQuery);
            } else {
                params.append('search', searchQuery);
            }
        }
        const response = await fetch(`/api/emails?${params}`, {
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
            const data = await response.json();
            displayEmails(data.items);
            setupPagination(data.current_page, data.total_pages);
            currentPage = data.current_page;
            totalPages = data.total_pages;
        } else {
            throw new Error('Failed to load emails');
        }
    } catch (error) {
        console.error('Error loading emails:', error);
        document.getElementById('emailList').innerHTML = 
            '<div class="no-emails">Error loading emails. Please try again.</div>';
    }
}

function getPreviewText(html) {
    // Strip all HTML tags and normalize whitespace
    const tmp = document.createElement('div');
    tmp.innerHTML = html || '';
    let text = tmp.textContent || tmp.innerText || '';
    // Remove all line breaks, tabs, and multiple spaces - replace with single space
    text = text.replace(/\s+/g, ' ').trim();
    return text;
}

function displayEmails(emails) {
    const emailList = document.getElementById('emailList');
    const actionsToolbar = document.getElementById('actionsToolbar');
    
    if (emails.length === 0) {
        emailList.innerHTML = '<div class="no-emails">No emails found.</div>';
        document.getElementById('pagination').style.display = 'none';
        if (actionsToolbar) actionsToolbar.style.display = 'none';
        return;
    }

    if (actionsToolbar) actionsToolbar.style.display = 'flex';

    emailList.innerHTML = `
        <div class="email-list">
            ${emails.map(email => {
                let previewSource = email.body_snippet || email.body || '';
                let previewText = getPreviewText(previewSource);
                return `
                <div class="email-item ${email.is_read ? '' : 'unread'}" onclick="viewEmail('${email.id}')">
                    <input type="checkbox" class="email-select" onclick="event.stopPropagation(); toggleEmailSelection('${email.id}')" ${selectedEmails.has(email.id) ? 'checked' : ''}>
                    <div class="email-content" style="width:100%">
                        <div class="mailbox-row-flex">
                            <div class="mailbox-fromto">
                                <div class="mailbox-from">${escapeHtml(email.sender)}</div>
                                <div class="mailbox-to">To: ${escapeHtml(email.recipient || email.to || '')}</div>
                            </div>
                            <div class="mailbox-subjectpreview">
                                <div class="mailbox-subject">${escapeHtml(email.subject || '(No Subject)')}</div>
                                <div class="mailbox-preview">${escapeHtml(truncateText(previewText, 100))}</div>
                            </div>
                            <div class="mailbox-size-time">
                                <div class="mailbox-size">${formatBytes(email.size_bytes || email.size || 0)}</div>
                                <div class="email-time">${formatDate(email.arrival_time)}</div>
                            </div>
                        </div>
                    </div>
                </div>
                `;
            }).join('')}
        </div>
    `;
}

function setupPagination(currentPage, totalPages) {
    const pagination = document.getElementById('pagination');
    pagination.style.display = 'flex';
    const maxPagesToShow = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxPagesToShow / 2));
    let endPage = Math.min(totalPages, startPage + maxPagesToShow - 1);
    if (endPage - startPage + 1 < maxPagesToShow) {
        startPage = Math.max(1, endPage - maxPagesToShow + 1);
    }
    let paginationHTML = `
        <div class="pagination-controls">
            <div class="pagination-info">
                <span class="page-info">Page ${currentPage} of ${Math.max(1, totalPages)}</span>
                <div class="page-size-control">
                    <span>Show:</span>
                    <select onchange="changePageSize(this.value)" id="pageSizeSelect">
                        <option value="10" ${currentPageSize === 10 ? 'selected' : ''}>10</option>
                        <option value="20" ${currentPageSize === 20 ? 'selected' : ''}>20</option>
                        <option value="50" ${currentPageSize === 50 ? 'selected' : ''}>50</option>
                        <option value="100" ${currentPageSize === 100 ? 'selected' : ''}>100</option>
                    </select>
                    <span>per page</span>
                </div>
            </div>
            <div class="pagination-buttons">
                <button onclick="loadEmails(1)" ${currentPage === 1 ? 'disabled' : ''}>First</button>
                <button onclick="loadEmails(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>Previous</button>
    `;
    for (let i = startPage; i <= endPage; i++) {
        paginationHTML += `<button onclick="loadEmails(${i})" ${i === currentPage ? 'class="active"' : ''}>${i}</button>`;
    }
    paginationHTML += `
                <button onclick="loadEmails(${currentPage + 1})" ${currentPage >= Math.max(1, totalPages) ? 'disabled' : ''}>Next</button>
                <button onclick="loadEmails(${Math.max(1, totalPages)})" ${currentPage >= Math.max(1, totalPages) ? 'disabled' : ''}>Last</button>
            </div>
        </div>
    `;
    pagination.innerHTML = paginationHTML;
}

function viewEmail(emailId) {
    window.location.href = `/email/${emailId}`;
}

function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('selectAll');
    const emailCheckboxes = document.querySelectorAll('.email-item .email-select');
    if (selectAllCheckbox.checked) {
        emailCheckboxes.forEach(checkbox => {
            checkbox.checked = true;
            const emailId = checkbox.closest('.email-item').onclick.toString().match(/'([^']+)'/)[1];
            selectedEmails.add(emailId);
        });
    } else {
        emailCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        selectedEmails.clear();
    }
    updateActionButtons();
}

function toggleEmailSelection(emailId) {
    if (selectedEmails.has(emailId)) {
        selectedEmails.delete(emailId);
    } else {
        selectedEmails.add(emailId);
    }
    updateSelectAllState();
    updateActionButtons();
}

function updateSelectAllState() {
    const selectAllCheckbox = document.getElementById('selectAll');
    const emailCheckboxes = document.querySelectorAll('.email-item .email-select');
    const checkedCount = document.querySelectorAll('.email-item .email-select:checked').length;
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = checkedCount > 0 && checkedCount === emailCheckboxes.length;
        selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < emailCheckboxes.length;
    }
}

function updateActionButtons() {
    const hasSelection = selectedEmails.size > 0;
    document.getElementById('deleteBtn').disabled = !hasSelection;
    document.getElementById('markReadBtn').disabled = !hasSelection;
    document.getElementById('markUnreadBtn').disabled = !hasSelection;
}

function changePageSize(newSize) {
    currentPageSize = parseInt(newSize);
    currentPage = 1;
    selectedEmails.clear();
    updateActionButtons();
    loadEmails(1);
}

async function markSelectedAsRead() {
    if (selectedEmails.size === 0) return;
    await markSelectedEmails(true);
}

async function markSelectedAsUnread() {
    if (selectedEmails.size === 0) return;
    await markSelectedEmails(false);
}

async function markSelectedEmails(readStatus) {
    if (selectedEmails.size === 0) return;
    try {
        const promises = Array.from(selectedEmails).map(emailId =>
            fetch(`/api/emails/${emailId}/read?read=${readStatus}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'  // Include HttpOnly cookies
            })
        );
        await Promise.all(promises);
        selectedEmails.clear();
        updateActionButtons();
        loadEmails(currentPage);
    } catch (error) {
        console.error('Error updating emails:', error);
        alert('Error updating emails. Please try again.');
    }
}

async function deleteSelected() {
    if (selectedEmails.size === 0) return;
    if (!confirm(`Are you sure you want to delete ${selectedEmails.size} email(s)?`)) return;
    try {
        const promises = Array.from(selectedEmails).map(emailId =>
            fetch(`/api/emails/${emailId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'same-origin'  // Include HttpOnly cookies
            })
        );
        await Promise.all(promises);
        selectedEmails.clear();
        updateActionButtons();
        loadEmails(currentPage);
    } catch (error) {
        console.error('Error deleting emails:', error);
        alert('Error deleting emails. Please try again.');
    }
}

function refreshEmails() {
    selectedEmails.clear();
    updateActionButtons();
    loadEmails(currentPage);
}

function handleSearch(event) {
    if (event.key === 'Enter') {
        const value = event.target.value.trim();
        searchQuery = value;
        currentPage = 1;
        loadEmails(1);
    }
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

function formatDate(dateString) {
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

function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substr(0, maxLength) + '...';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
