import os.path
import re
import json
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import time
print("🕒 Script started at:", time.strftime("%Y-%m-%d %H:%M:%S"))

# ----------------------------------------
# CONFIG
# ----------------------------------------
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send'
]

REPLIED_FILE = 'replied.json'
EMAIL_TEMPLATE = """Hi {username},

This is Bunty from Bili Plugins.

We saw that your trial of this plugin has ended. 
Was the plugin useful for you?

If not, we would like to know if something is missing that we could add to our plugin.

Please let us know. Any feedback would be appreciated.

Thank You.
Bili Plugins
Website: https://biliplugins.com/
Twitter(X): https://twitter.com/bili_plugins/
"""

# Toggle test mode
TEST_MODE = False
TEST_EMAIL = "yourtestemail@example.com"  # Replace with your test email

# ----------------------------------------
# HELPERS
# ----------------------------------------
def extract_username(subject_line):
    match = re.search(r'Trial expired by (.+)', subject_line)
    return match.group(1).strip() if match else None

def get_header(headers, name):
    return next((h['value'] for h in headers if h['name'].lower() == name.lower()), None)

def create_reply_message(to, subject, body_text, thread_id, message_id):
    message = MIMEText(body_text)
    message['To'] = to
    message['Subject'] = subject
    message['In-Reply-To'] = message_id
    message['References'] = message_id

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {
        'raw': raw_message,
        'threadId': thread_id
    }

def send_reply(service, to, subject, body, thread_id, message_id):
    reply_msg = create_reply_message(to, subject, body, thread_id, message_id)
    service.users().messages().send(userId='me', body=reply_msg).execute()
    print(f"✅ Sent reply to: {to}")

def load_replied_ids():
    if os.path.exists(REPLIED_FILE):
        with open(REPLIED_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_replied_ids(replied_ids):
    with open(REPLIED_FILE, 'w') as f:
        json.dump(list(replied_ids), f)

# ----------------------------------------
# MAIN FUNCTION
# ----------------------------------------
def read_and_reply():
    from datetime import datetime, timedelta

    seven_days_ago = (datetime.utcnow() - timedelta(days=7)).strftime('%Y/%m/%d')
    query = f'subject:"Trial expired by" after:{seven_days_ago}'

    # Authenticate
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('gmail', 'v1', credentials=creds)

    replied_ids = load_replied_ids()

    # Fetch matching messages
    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=1000
    ).execute()

    messages = results.get('messages', [])

    if not messages:
        print("📭 No matching emails.")
        return

    for msg in messages:
        msg_id = msg['id']
        if msg_id in replied_ids:
            print(f"⏭️ Already replied to: {msg_id}")
            continue

        msg_data = service.users().messages().get(userId='me', id=msg_id).execute()
        headers = msg_data['payload']['headers']

        subject = get_header(headers, 'Subject')
        if not subject:
            continue

        # Skip replies
        if subject.lower().startswith("re:"):
            print(f"🔁 Skipping already replied email: {subject}")
            continue

        reply_to = get_header(headers, 'reply-to') or get_header(headers, 'from')
        username = extract_username(subject)

        if not username or not reply_to:
            print(f"⚠️ Missing username or reply-to in email: {subject}")
            continue

        print(f"\n📬 Subject: {subject}")
        print(f"📨 Reply-To: {reply_to}")
        print(f"🧑 Username: {username}")

        message_id = get_header(headers, 'Message-ID')
        thread_id = msg_data.get('threadId')

        if not message_id or not thread_id:
            print("⚠️ Missing message ID or thread ID, cannot reply.")
            continue

        final_recipient = TEST_EMAIL if TEST_MODE else reply_to
        subject_reply = f"Re: {subject}"
        body = EMAIL_TEMPLATE.format(username=username)

        print(f"✉️ Sending reply to: {final_recipient}\n")

        send_reply(service, final_recipient, subject_reply, body, thread_id, message_id)

        print("📌 Reply recorded.")
        replied_ids.add(msg_id)

    save_replied_ids(replied_ids)

# ----------------------------------------
# RUN
# ----------------------------------------
if __name__ == "__main__":
    read_and_reply()
