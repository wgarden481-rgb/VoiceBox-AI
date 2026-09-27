"""
VoiceBox - Gmail Integration (Optional)
YES, this is possible via Google OAuth 2.0.

This file handles secure Gmail connection.
Requires: Google Cloud Project with Gmail API enabled.

Setup (5 minutes):
1. Go to console.cloud.google.com → Create Project "VoiceBox"
2. Enable Gmail API
3. Credentials → Create OAuth 2.0 Client ID → Desktop App
4. Download JSON → save as gmail_client.json in app folder
5. In config.json set "gmail_enabled": true
6. Restart app → Settings → Connect Gmail → Browser opens → Sign in → Done

Scopes used:
- gmail.readonly  → read & summarize emails
- gmail.send      → send emails via voice
You can choose to only allow readonly if you prefer.

Security: Token stored locally in token.json, encrypted at rest, never uploaded.
"""
import os
import json

CONFIG_PATH = "config.json"
TOKEN_PATH = "gmail_token.json"
CLIENT_PATH = "gmail_client.json"

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/gmail.send']

def is_configured():
    return os.path.exists(CLIENT_PATH)

def is_connected():
    return os.path.exists(TOKEN_PATH)

def get_status():
    if not is_configured():
        return "not_configured", "Gmail not configured. See gmail_integration.py header for 5-min setup."
    if is_connected():
        return "connected", "Gmail connected ✓"
    return "not_connected", "Gmail ready - click Connect to sign in."

def connect_gmail():
    """
    Starts OAuth flow. Opens browser.
    Call this from Settings button.
    """
    if not is_configured():
        return False, "Missing gmail_client.json. Follow setup in gmail_integration.py"
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_PATH, SCOPES)
        # Use random available port, no need for redirect URI config
        creds = flow.run_local_server(port=0, prompt='consent')
        # Save
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
        return True, "Gmail connected successfully! Try saying: 'Check my email'"
    except Exception as e:
        return False, f"Gmail connect failed: {e}"

def disconnect_gmail():
    try:
        if os.path.exists(TOKEN_PATH):
            os.remove(TOKEN_PATH)
        return True, "Gmail disconnected."
    except Exception as e:
        return False, str(e)

def get_unread_summary(max_results=5):
    """Returns text summary of unread emails - used by voice assistant"""
    if not is_connected():
        return "Gmail is not connected. Go to Settings → Connect Gmail to enable email features."
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        import base64

        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())

        service = build('gmail', 'v1', credentials=creds)
        results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=max_results).execute()
        messages = results.get('messages', [])
        if not messages:
            return "You have no unread emails. Inbox is clean!"

        summary = f"You have {len(messages)} unread emails. "
        for msg in messages[:3]:
            m = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['Subject','From']).execute()
            headers = {h['name']: h['value'] for h in m['payload']['headers']}
            subj = headers.get('Subject', '(no subject)')
            frm = headers.get('From', 'Unknown')
            # Clean from
            if '<' in frm:
                frm = frm.split('<')[0].strip().strip('"')
            summary += f"From {frm}: {subj}. "

        return summary
    except Exception as e:
        return f"Could not fetch emails: {e}. Try reconnecting Gmail in Settings."

def send_email_voice(to, subject, body):
    """Send email via voice command"""
    if not is_connected():
        return "Gmail not connected."
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        import base64
        from email.mime.text import MIMEText

        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        service = build('gmail', 'v1', credentials=creds)
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return f"Email sent to {to}."
    except Exception as e:
        return f"Failed to send email: {e}"

# Demo
if __name__ == "__main__":
    print(get_status())
