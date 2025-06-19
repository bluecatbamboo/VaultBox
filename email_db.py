"""Encrypted Email Database Module.

Provides SQLite-based encrypted storage for emails with tokenized search capabilities.
Implements field-level encryption and secure search token generation.
"""

import hashlib
import hmac
import json
import logging
import math
import os
import re
import sqlite3
import uuid
from typing import Optional, Dict, List, Any, Set

from cryptography.fernet import Fernet

# Configure module logging
logger = logging.getLogger(__name__)


class EmailDB:
    """SQLite database for encrypted email storage with tokenized search.
    
    Provides secure storage of email data with field-level encryption and
    searchable tokens for privacy-preserving full-text search.
    """
    
    def __init__(self, db_path: str = "data/emails.db", max_size_mb: int = 1024, encryption_key: Optional[str] = None):
        """Initialize database connection and encryption.
        
        Args:
            db_path: Path to SQLite database file.
            max_size_mb: Maximum database size in megabytes.
            encryption_key: Base64-encoded encryption key for data protection.
        """
        self.db_path = db_path
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.encryption_key = encryption_key.encode() if encryption_key else Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        
        # Derive separate key for search tokens using PBKDF2
        self.token_key = hashlib.pbkdf2_hmac('sha256', self.encryption_key, b'search_tokens', 100000)[:32]
        
        self._create_table()

    def _create_table(self) -> None:
        """Create database tables if they don't exist."""
        """Create emails and search token tables."""
        # Main encrypted storage (everything encrypted)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY,
                sender BLOB NOT NULL,
                recipient BLOB NOT NULL,
                subject BLOB,
                body BLOB,
                read BOOLEAN DEFAULT 0,
                arrival_time TEXT NOT NULL,
                tags TEXT DEFAULT '[]'
            )
        ''')
        
        # Encrypted search tokens (replaces FTS table for security)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS search_tokens (
                email_id TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                token_source TEXT NOT NULL,
                FOREIGN KEY (email_id) REFERENCES emails (id)
            )
        ''')
        
        # Create index for fast token lookup
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_token_hash ON search_tokens(token_hash)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_email_tokens ON search_tokens(email_id)')
        
        self.conn.commit()

    def _decrypt_if_needed(self, data: Optional[str]) -> str:
        """Decrypt data if cipher is available."""
        if not self.cipher or not data:
            return data or ""
        try:
            # Handle both string and bytes input
            if isinstance(data, str):
                return self.cipher.decrypt(data.encode()).decode()
            else:
                return self.cipher.decrypt(data).decode()
        except Exception:
            return data if isinstance(data, str) else data.decode() if data else ""

    def _encrypt_if_needed(self, data: Optional[str]) -> bytes:
        """Encrypt data if cipher is available."""
        if not self.cipher or not data:
            return data.encode() if data else b""
        try:
            return self.cipher.encrypt(data.encode())
        except Exception:
            return data.encode() if data else b""

    def _enforce_max_size(self) -> None:
        """Delete oldest emails to maintain size limit."""
        while os.path.exists(self.db_path) and os.path.getsize(self.db_path) > self.max_size_bytes:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM emails ORDER BY arrival_time ASC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                break
            email_id = row[0]
            cursor.execute("DELETE FROM emails WHERE id = ?", (email_id,))
            cursor.execute("DELETE FROM search_tokens WHERE email_id = ?", (email_id,))
            self.conn.commit()

    def _extract_tokens(self, text: str) -> Set[str]:
        """Extract searchable tokens from text."""
        if not text:
            return set()
            
        # Clean and normalize
        text = text.lower().strip()
        tokens = set()
        
        # Extract email addresses first (preserve full structure)
        email_pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        emails = re.findall(email_pattern, text)
        for email in emails:
            tokens.add(email)
            # Also add local part and domain separately for partial matching
            if '@' in email:
                local_part, domain = email.split('@', 1)
                if len(local_part) >= 3:
                    tokens.add(local_part)
                if len(domain) >= 3:
                    tokens.add(domain)
        
        # Extract regular words (3+ chars, alphanumeric)
        words = re.findall(r'\b\w{3,}\b', text)
        tokens.update(words)
        
        # Add bigrams for phrase search (only for regular words, not emails)
        word_list = [w for w in words if len(w) >= 2]
        for i in range(len(word_list) - 1):
            tokens.add(f"{word_list[i]}_{word_list[i+1]}")
            
        return tokens

    def _hash_token(self, token: str, source: str) -> str:
        """Create deterministic hash of search token."""
        # Include source to differentiate subject:budget from body:budget
        token_with_source = f"{source}:{token}"
        return hmac.new(self.token_key, token_with_source.encode(), hashlib.sha256).hexdigest()[:16]

    def _store_search_tokens(self, email_id: str, sender: str, recipient: str, subject: str, body: str):
        """Extract and store encrypted search tokens."""
        
        # Extract tokens from each field
        sender_tokens = self._extract_tokens(sender)
        recipient_tokens = self._extract_tokens(recipient) 
        subject_tokens = self._extract_tokens(subject)
        body_tokens = self._extract_tokens(body)
        
        # Store encrypted tokens
        all_tokens = [
            (sender_tokens, 'sender'),
            (recipient_tokens, 'recipient'),
            (subject_tokens, 'subject'),
            (body_tokens, 'body')
        ]
        
        for tokens, source in all_tokens:
            for token in tokens:
                token_hash = self._hash_token(token, source)
                self.conn.execute('''
                    INSERT INTO search_tokens (email_id, token_hash, token_source)
                    VALUES (?, ?, ?)
                ''', (email_id, token_hash, source))

    def insert_email(self, sender: str, recipient: str, subject: str, body: str, arrival_time: str, tags: Optional[List[str]] = None) -> str:
        """Insert new email and return generated ID."""
        email_id = str(uuid.uuid4())[:23].replace('-', '')
        tags_json = json.dumps(tags or [])
        
        # Store encrypted data in main table
        encrypted_sender = self._encrypt_if_needed(sender)
        encrypted_recipient = self._encrypt_if_needed(recipient)
        encrypted_subject = self._encrypt_if_needed(subject)
        encrypted_body = self._encrypt_if_needed(body)
        
        self.conn.execute(
            "INSERT INTO emails (id, sender, recipient, subject, body, read, arrival_time, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (email_id, encrypted_sender, encrypted_recipient, encrypted_subject, encrypted_body, False, arrival_time, tags_json)
        )
        
        # For tokenized search, decrypt data if it comes in encrypted (from Redis worker)
        plaintext_sender = self._decrypt_if_needed(sender)
        plaintext_recipient = self._decrypt_if_needed(recipient)
        plaintext_subject = self._decrypt_if_needed(subject)
        plaintext_body = self._decrypt_if_needed(body)
        
        # Store encrypted search tokens instead of plaintext FTS
        self._store_search_tokens(email_id, plaintext_sender, plaintext_recipient, plaintext_subject, plaintext_body)
        
        self.conn.commit()
        self._enforce_max_size()
        return email_id

    def insert_email_with_id(self, email_id: str, sender: str, recipient: str, subject: str, body: str, arrival_time: str, tags: Optional[List[str]] = None) -> str:
        """Insert email with provided ID and return it."""
        tags_json = json.dumps(tags or [])
        
        # Store encrypted data in main table  
        encrypted_sender = self._encrypt_if_needed(sender)
        encrypted_recipient = self._encrypt_if_needed(recipient)
        encrypted_subject = self._encrypt_if_needed(subject)
        encrypted_body = self._encrypt_if_needed(body)
        
        self.conn.execute(
            "INSERT INTO emails (id, sender, recipient, subject, body, read, arrival_time, tags) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (email_id, encrypted_sender, encrypted_recipient, encrypted_subject, encrypted_body, False, arrival_time, tags_json)
        )
        
        # For tokenized search, use plaintext data (data comes unencrypted from Redis now)
        self._store_search_tokens(email_id, sender, recipient, subject, body)
        
        self.conn.commit()
        self._enforce_max_size()
        return email_id

    def get_email_by_id(self, email_id: str, recipient_username: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get single email by ID with optional recipient filter."""
        query = "SELECT id, sender, recipient, subject, body, read, arrival_time, tags FROM emails WHERE id = ?"
        params = [email_id]
        
        if recipient_username:
            query += " AND recipient = ?"
            params.append(recipient_username)
            
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        if not row:
            return None

        tags_list = json.loads(row[7]) if row[7] else []
        body_text = self._decrypt_if_needed(row[4])
        
        return {
            "id": row[0],
            "sender": self._decrypt_if_needed(row[1]),
            "recipient": self._decrypt_if_needed(row[2]),
            "subject": self._decrypt_if_needed(row[3]),
            "body": body_text,
            "is_read": bool(row[5]),
            "arrival_time": row[6],
            "tags": tags_list,
            "size_bytes": len(body_text.encode('utf-8'))
        }

    def mark_email_as_read(self, email_id: str, recipient_username: Optional[str] = None, read_status: bool = True) -> bool:
        """Mark email as read/unread."""
        query = "UPDATE emails SET read = ? WHERE id = ?"
        params = [read_status, email_id]
        
        if recipient_username:
            query += " AND recipient = ?"
            params.append(recipient_username)
            
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_email(self, email_id: str, recipient_username: Optional[str] = None) -> bool:
        """Delete email by ID."""
        query = "DELETE FROM emails WHERE id = ?"
        params = [email_id]
        
        if recipient_username:
            # Need to encrypt recipient for comparison
            encrypted_recipient = self._encrypt_if_needed(recipient_username)
            query += " AND recipient = ?"
            params.append(encrypted_recipient)
            
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        
        # Also delete from search tokens
        if cursor.rowcount > 0:
            cursor.execute("DELETE FROM search_tokens WHERE email_id = ?", (email_id,))
        
        self.conn.commit()
        return cursor.rowcount > 0

    def get_emails_for_recipient(
        self,
        recipient_username: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "arrival_time",
        sort_order: str = "DESC",
        search_query: Optional[str] = None,
        advanced_query: Optional[str] = None,
        is_read: Optional[bool] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated emails with tokenized search and sorting."""
        offset = (page - 1) * page_size
        where_clauses = []
        params = []
        
        # Handle search using tokenized approach
        if search_query or advanced_query:
            matching_email_ids, is_read_from_advanced = self._search_by_tokens(search_query, advanced_query)
            
            # If is_read was specified in advanced query, use that value
            if is_read_from_advanced is not None:
                is_read = is_read_from_advanced
            
            if matching_email_ids:
                placeholders = ','.join(['?' for _ in matching_email_ids])
                where_clauses.append(f"emails.id IN ({placeholders})")  
                params.extend(matching_email_ids)
            else:
                # No matches found
                return {
                    "items": [],
                    "total_items": 0, 
                    "total_pages": 0,
                    "current_page": page,
                    "page_size": page_size
                }
        
        # Other filters
        if recipient_username:
            # Need to search by encrypted recipient
            encrypted_recipient = self._encrypt_if_needed(recipient_username)
            where_clauses.append("emails.recipient = ?")
            params.append(encrypted_recipient)
            
        if is_read is not None:
            where_clauses.append("emails.read = ?")
            params.append(1 if is_read else 0)
            
        if date_from:
            where_clauses.append("emails.arrival_time >= ?")
            params.append(date_from)
            
        if date_to:
            where_clauses.append("emails.arrival_time <= ?")
            params.append(date_to)
        
        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        
        # Count and fetch
        count_sql = f"SELECT COUNT(*) FROM emails {where_sql}"
        cursor = self.conn.cursor()
        cursor.execute(count_sql, params)
        total_items = cursor.fetchone()[0]
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 0
        
        select_sql = f'''
            SELECT id, sender, recipient, subject, body, read, arrival_time, tags 
            FROM emails {where_sql} 
            ORDER BY {sort_by} {sort_order} 
            LIMIT ? OFFSET ?
        '''
        params.extend([page_size, offset])
        
        cursor.execute(select_sql, params)
        rows = cursor.fetchall()
        
        # Decrypt results for display
        emails = []
        for row in rows:
            try:
                email_id, enc_sender, enc_recipient, enc_subject, enc_body, read, arrival_time, tags = row
                
                # Decrypt content
                sender = self._decrypt_if_needed(enc_sender)
                recipient = self._decrypt_if_needed(enc_recipient) 
                subject = self._decrypt_if_needed(enc_subject)
                body = self._decrypt_if_needed(enc_body)
                
                # Clean body for snippet
                clean_body = re.sub(r'<[^>]+>', '', body)
                clean_body = re.sub(r'\s+', ' ', clean_body).strip()
                body_snippet = (clean_body[:100] + "...") if len(clean_body) > 100 else clean_body
                
                tags_list = json.loads(tags) if tags else []
                
                emails.append({
                    "id": email_id,
                    "sender": sender,
                    "recipient": recipient,
                    "subject": subject,
                    "body_snippet": body_snippet,
                    "is_read": bool(read),
                    "arrival_time": arrival_time,
                    "tags": tags_list,
                    "size_bytes": len(body.encode('utf-8'))
                })
                
            except Exception as e:
                logger.error(f"Failed to decrypt email {email_id}: {e}")
                continue
        
        return {
            "items": emails,
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size
        }

    def _search_by_tokens(self, search_query: Optional[str], advanced_query: Optional[str]) -> tuple[List[str], Optional[bool]]:
        """Search using encrypted tokens. Returns (email_ids, is_read_filter)."""
        
        if advanced_query:
            return self._advanced_token_search(advanced_query)
        elif search_query:
            return self._simple_token_search(search_query), None
        
        return [], None

    def _simple_token_search(self, query: str) -> List[str]:
        """Simple search using tokens."""
        
        query_tokens = self._extract_tokens(query)
        if not query_tokens:
            return []
        
        # Check if query is a full email address for exact matching
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_full_email = re.match(email_pattern, query.strip())
        
        if is_full_email:
            # For full email addresses, search for exact match first
            exact_email_token = query.lower().strip()
            exact_hashes = []
            for source in ['sender', 'recipient']:  # Only search in email fields
                exact_hashes.append(self._hash_token(exact_email_token, source))
            
            placeholders = ','.join(['?' for _ in exact_hashes])
            cursor = self.conn.execute(f'''
                SELECT DISTINCT email_id 
                FROM search_tokens 
                WHERE token_hash IN ({placeholders})
            ''', exact_hashes)
            
            exact_matches = [row[0] for row in cursor.fetchall()]
            if exact_matches:
                return exact_matches
        
        # Fallback to regular token search for partial matches or non-email queries
        token_hashes = []
        for token in query_tokens:
            for source in ['subject', 'body', 'sender', 'recipient']:
                token_hashes.append(self._hash_token(token, source))
        
        # Find matching emails
        if token_hashes:
            placeholders = ','.join(['?' for _ in token_hashes])
            cursor = self.conn.execute(f'''
                SELECT DISTINCT email_id 
                FROM search_tokens 
                WHERE token_hash IN ({placeholders})
            ''', token_hashes)
            
            return [row[0] for row in cursor.fetchall()]
        
        return []

    def _advanced_token_search(self, advanced_query: str) -> tuple[List[str], Optional[bool]]:
        """Advanced search with field-specific tokens. Returns (email_ids, is_read_filter)."""
        
        field_map = {"from": "sender", "to": "recipient", "sender": "sender", 
                    "recipient": "recipient", "subject": "subject", "body": "body"}
        
        parts = [p.strip() for p in advanced_query.split(';') if p.strip()]
        all_token_hashes = []
        is_read_filter = None
        
        for part in parts:
            # Handle is_read filters
            if part.lower().startswith('is_read:'):
                value = part[8:].strip().lower()  # Remove 'is_read:'
                if value in ('true', '1', 'yes'):
                    is_read_filter = True
                elif value in ('false', '0', 'no'):
                    is_read_filter = False
                continue
                
            for alias, field in field_map.items():
                if part.lower().startswith(f"{alias}:"):
                    value = part[len(alias)+1:].strip()
                    
                    # Handle quoted values
                    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    # Check if value is a full email address for exact matching
                    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                    is_full_email = re.match(email_pattern, value.strip())
                    
                    if is_full_email and field in ['sender', 'recipient']:
                        # For full email addresses in sender/recipient fields, prioritize exact match
                        exact_email_token = value.lower().strip()
                        token_hash = self._hash_token(exact_email_token, field)
                        all_token_hashes.append(token_hash)
                    else:
                        # Regular tokenization for other cases
                        tokens = self._extract_tokens(value)
                        for token in tokens:
                            token_hash = self._hash_token(token, field)
                            all_token_hashes.append(token_hash)
                    break
            else:
                # Free text search across all fields
                tokens = self._extract_tokens(part)
                for token in tokens:
                    for source in ['subject', 'body', 'sender', 'recipient']:
                        token_hash = self._hash_token(token, source)
                        all_token_hashes.append(token_hash)
        
        email_ids = []
        if all_token_hashes:
            placeholders = ','.join(['?' for _ in all_token_hashes])
            cursor = self.conn.execute(f'''
                SELECT DISTINCT email_id 
                FROM search_tokens 
                WHERE token_hash IN ({placeholders})
            ''', all_token_hashes)
            
            email_ids = [row[0] for row in cursor.fetchall()]
        elif is_read_filter is not None and not all_token_hashes:
            # If only is_read filter is specified, return all email IDs
            cursor = self.conn.execute('SELECT id FROM emails')
            email_ids = [row[0] for row in cursor.fetchall()]
        
        return email_ids, is_read_filter

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()
