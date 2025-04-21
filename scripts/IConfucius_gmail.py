"""IConfucius: Gmail integration for checking quote topics.

Preparations we had to take to enable this python script to read & send emails:

    Step 1: In GCP, for the "onicai-IConfucius" project, we enabled the 'Gmail API'
            https://console.cloud.google.com/apis/api/gmail.googleapis.com/metrics?project=onicai-iconfucius&chat=true

    Step 2: In GCP, for the "onicai-IConfucius" project, we created a Service Account
            https://console.cloud.google.com/iam-admin/serviceaccounts?chat=true&project=onicai-iconfucius

    Step 3: In GCP, for the Service Account, we created a key, and downloaded the JSON file
             This file contains the private key for your service account.
             Save this file in "scripts/secret/service-account-iconfucius-gmail-access.json"

    Step 4: Turned on 2-step verification for the Gmail account and created an App Password
            https://myaccount.google.com/apppasswords
             App name = IConfucius Agent
             Stored the app password in the file "scripts/.env" as "GMAIL_APP_PASSWORD"

"""
# Import necessary libraries
import imaplib
import email
import os
from pathlib import Path
from dotenv import load_dotenv
from email.header import decode_header
from email.utils import parsedate_to_datetime, formataddr
import json
from datetime import datetime, timezone as dt_timezone, timedelta # Import timezone (aliased) and timedelta
import pytz  # Import pytz for utc handling
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pprint


SCRIPT_PATH = Path(__file__).parent

# Load environment variables from .env file
load_dotenv()

# Gmail credentials
GMAIL_ADDRESS = os.getenv('GMAIL_ADDRESS')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')

# Service account JSON file path
# TODO: Rewrite the script to use the service account for authentication instead of the app password
SERVICE_ACCOUNT_FILE = SCRIPT_PATH / 'secret/service-account-iconfucius-gmail-access.json'

# IMAP server details
IMAP_SERVER = 'imap.gmail.com'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

# File to store last checked datetime
LAST_CHECKED_FILE = SCRIPT_PATH / 'secret/db/IConfucius_gmail_last_checked_timestamp.json'
# File to store topics
TOPICS_FILE = SCRIPT_PATH / 'secret/db/IConfucius_gmail_wisdom_topics.json'

# Maximum lookback days
MAX_LOOKBACK_DAYS = 1


def extract_quote_topic(subject):
    try:
        return subject.split(': ')[1].strip()
    except IndexError:
        return None

def clean_header(header):
    """Decode and clean header strings."""
    decoded_parts = decode_header(header)
    parts = []
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            try:
                if encoding:
                    part = part.decode(encoding)
                else:
                    part = part.decode('utf-8', 'ignore')
            except UnicodeDecodeError:
                part = part.decode('latin1', 'ignore')  # Fallback to latin1 if utf-8 fails
        parts.append(str(part))  # Ensure everything is a string
    return ''.join(parts)

def load_last_checked():
    """Loads the last checked datetime from the file."""
    try:
        with open(LAST_CHECKED_FILE, 'r') as f:
            data = json.load(f)
            last_checked_str = data.get('last_checked')
            if last_checked_str:
                # Parse as UTC and then convert to local timezone-aware datetime
                last_checked_utc = datetime.strptime(last_checked_str, '%Y-%m-%d %H:%M:%S %Z')
                last_checked_utc = pytz.utc.localize(last_checked_utc)  # Make timezone-aware
                local_tz = datetime.now(dt_timezone.utc).astimezone().tzinfo # Get system local timezone
                last_checked_local = last_checked_utc.astimezone(local_tz) # Convert to local tz
                return last_checked_local
            else:
                return None
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

def save_last_checked(now_local):
    """Saves the last checked datetime to the file."""
    with open(LAST_CHECKED_FILE, 'w') as f:
        data = {"last_checked": now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}
        json.dump(data, f)
    print(f"Updated last checked time to: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
def save_gmail_topics(topics):
    """Saves the gmail topics to a JSON file."""
    with open(TOPICS_FILE, 'w') as f:
        json.dump(topics, f, indent=4)

def load_gmail_topics():
    """Loads existing gmail topics from a JSON file, if it exists."""
    try:
        with open(TOPICS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []

def get_gmail_topics():
    """
    This function checks for new quote topics in Gmail and returns a list of topics.
    It uses the Google Cloud Pub/Sub API to listen for messages on a specific topic.

    It returns a list of dictionaries, with each dictionary representing an email
    containing a quote topic.  Each dictionary will contain the following keys:

        'topic': The extracted quote topic from the subject.
        'sender': The email address of the sender.
        'subject': The full subject line of the email.
        'date': The date the email was sent.
        'message_id': The Message-ID header of the email (unique identifier).
        'content': The plain text content of the email.
        'quote': The quote generated for the topic (default is None).
        'replied': A boolean indicating if a reply was sent (default is False).
        'posted_to_odin': A boolean indicating if the quote was posted to Odin (default is False).
        'posted_to_odin_date': The date the quote was posted to Odin (default is None).
        'posted_to_X': A boolean indicating if the quote was posted to X (default is False).
        'posted_to_X_date': The date the quote was posted to X (default is None).
    """

    # Print a message indicating the start of the process
    print("-------------------------------------------------------")
    print("IConfucius: Checking for new quote topics in Gmail...")

    gmail_topics = load_gmail_topics()  # Load existing topics
    last_checked = load_last_checked() # Returns timezone-aware local time or None

    # Get the system's local timezone
    local_tz = datetime.now(dt_timezone.utc).astimezone().tzinfo
    # Calculate lookback_days_ago as a timezone-aware datetime in the local timezone
    now_local = datetime.now(local_tz)
    lookback_days_ago = now_local - timedelta(days=MAX_LOOKBACK_DAYS) # Now timezone-aware

    try:
        # Connect to the IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

        # Select the inbox
        mail.select('inbox')

        # Build the search query
        search_query = 'SUBJECT "wisdom quote:"'
        if last_checked:
            # Determine which date to use: last_checked or lookback_days_ago
            since_date = max(last_checked, lookback_days_ago)

            # Format date for Gmail IMAP search.  Gmail wants the date in the form "%d-%b-%Y"
            date_str = since_date.strftime("%d-%b-%Y")
            search_query += f' SINCE "{date_str}"'  #Added space before since!
        else:
            # If no last_checked, use lookback_days_ago
            date_str = lookback_days_ago.strftime("%d-%b-%Y")
            search_query += f' SINCE "{date_str}"'  #Added space before since!

        _, selected_emails = mail.search(None, search_query)


        for num in selected_emails[0].split():
            _, email_data = mail.fetch(num, '(RFC822)')
            raw_email = email_data[0][1]
            raw_email_string = raw_email.decode('utf-8')
            email_message = email.message_from_string(raw_email_string)

            # Extract information
            sender = clean_header(email_message['from'])
            subject = clean_header(email_message['subject'])
            # skip if the subject does not start with "wisdom quote:" - use case insensitive check
            if not subject.lower().startswith("wisdom quote:"):
                print(f"Skipping email with subject: {subject}")
                continue

            date = clean_header(email_message['date'])
            message_id = clean_header(email_message['Message-ID'])

            # Skip if the message ID is already in the list of topics
            if any(topic['message_id'] == message_id for topic in gmail_topics):
                print(f"Email is already in the list - message ID: {message_id}")
                continue

            # Convert email date string to datetime object
            try:
                email_dt = parsedate_to_datetime(date)
            except Exception as e:
                print(f"Failed to parse date '{date}': {e}")
                continue

            # Skip emails older than last_checked
            if last_checked and email_dt <= last_checked:
                print(f"Skipping email from {email_dt} — before last checked time {last_checked}")
                continue



            # Extract the quote topic
            quote_topic = extract_quote_topic(subject)

            # NOT YET--- Extract the body of the email
            content = ""
            # if email_message.is_multipart():
            #     for part in email_message.walk():
            #         ctype = part.get_content_type()
            #         cdispo = str(part.get('Content-Disposition'))

            #         if ctype == 'text/plain' and 'attachment' not in cdispo:
            #             try:
            #                 content = part.get_payload(decode=True).decode()
            #             except:
            #                 content = part.get_payload(decode=True).decode('latin1', 'ignore') #added try except block

            #             break  # Only take the first text/plain part
            # else:
            #     try:
            #         content = email_message.get_payload(decode=True).decode()
            #     except:
            #          content = email_message.get_payload(decode=True).decode('latin1', 'ignore') #added try except block


            if quote_topic:
                print(f'Found new quote topic: {quote_topic}')
                gmail_topics.append({
                    "topic": quote_topic,
                    "language_code": "en", # Default to English
                    "sender": sender,
                    "subject": subject,
                    "date": date,
                    "message_id": message_id,
                    "content": content,
                    "quote": None,
                    "replied": False,
                    "tweet_id": None,
                    "tweet_url": None,
                })
            else:
                print(f'No quote topic found in subject: {subject}')

        # Close the connection
        mail.close()
        mail.logout()

        #Save last checked timestamp
        save_last_checked(now_local)
        save_gmail_topics(gmail_topics) # Save updated topics

    except Exception as e:
        print(f'An error occurred: {e}')

    return gmail_topics

def gmail_reply_to_sender(gmail_topic):
    """
    Sends a reply email to the sender of the topic suggestion with the generated quote.

    Args:
        gmail_topic (dict): A dictionary containing the details of the received email
                           and the generated quote. It should have at least 'sender',
                           'subject', and 'quote' keys.
    """
    sender_email = gmail_topic.get('sender')
    original_subject = gmail_topic.get('subject')
    generated_quote = gmail_topic.get('quote')
    tweet_url = gmail_topic.get('tweet_url')
    ps = ""
    if tweet_url:
        ps = f"\nps. I also posted your personalized quote on X at {tweet_url}"

    if not sender_email or not generated_quote:
        print("Error: Cannot reply. Missing sender email or generated quote.")
        return

    recipient_email = sender_email
    reply_subject = f"Re: {original_subject}"
    body = f"""
Greetings!

Thank you for suggesting the topic: "{gmail_topic.get('topic')}".

Here is a wisdom quote on that topic:

"{generated_quote}"

May this bring you insight and happiness.

Sincerely,
IConfucius (Agent)
{ps}

--
IConfucius is a project by onicai (https://www.onicai.com/#/iconfucius).
"""

    msg = MIMEMultipart()
    msg['From'] = formataddr(('IConfucius (Agent)', GMAIL_ADDRESS))
    msg['To'] = recipient_email
    msg['Subject'] = reply_subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, recipient_email, msg.as_string())
            print(f"Successfully sent reply to {recipient_email} for topic: {gmail_topic.get('topic')}")
    except Exception as e:
        print(f"Error sending reply email: {e}")


if __name__ == '__main__':
    topics = get_gmail_topics()
    pprint.pprint(topics)
