import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.header import decode_header
import time
from dotenv import load_dotenv
import os
import openai
from email_reply_parser import parse_reply

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# IMAP server configuration (for reading emails)
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
EMAIL_ACCOUNT = os.getenv(
    "BETA_AI_EMAIL_ACCOUNT"
)  # Use environment variables or a secure method for actual credentials
PASSWORD = os.getenv(
    "BETA_AI_PASSWORD"
)  # Use environment variables or a secure method for actual credentials

# SMTP server configuration (for sending emails)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


# Function to automatically reply to an email
def auto_reply(mail, email_id):
    try:
        result, data = mail.fetch(
            email_id, "(BODY.PEEK[])"
        )  # Use BODY.PEEK[] to avoid marking as seen
        if result == "OK":
            print("Responding to email ID", email_id)
            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            from_email = email.utils.parseaddr(msg["From"])[1]
            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()
            # reply_subject = f"Re: {subject}"
            reply_subject = subject

            # Get the In-Reply-To header to determine the email thread
            in_reply_to = msg.get("In-Reply-To")
            references = msg.get("References")
            thread_id = in_reply_to if in_reply_to else references

            # Extract the content of the received email along with the sender's email
            email_content = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))

                    if (
                        content_type == "text/plain"
                        and "attachment" not in content_disposition
                    ):
                        email_content += part.get_payload(decode=True).decode("UTF-8")
            else:
                email_content = msg.get_payload(decode=True).decode("UTF-8")

            original = email_content
            latest_email = parse_reply(email_content).strip()
            email_content = "Latest email:\n\n" + latest_email
            original = original.strip()
            if latest_email != original:
                if original.startswith(latest_email):
                    email_content += "\n\nHistory:\n\n" + original[len(latest_email) :]

            print("\n\n", email_content, "\n\n")

            # # Check if there's a history of messages
            # existing_history = ""
            # if thread_id:
            #     # Fetch previous emails in the thread
            #     result, thread_data = mail.fetch(thread_id, "(BODY.PEEK[])")
            #     if result == "OK":
            #         thread_msg = email.message_from_bytes(thread_data[0][1])
            #         if thread_msg.is_multipart():
            #             for part in thread_msg.walk():
            #                 content_type = part.get_content_type()
            #                 content_disposition = str(part.get("Content-Disposition"))

            #                 if (
            #                     content_type == "text/plain"
            #                     and "attachment" not in content_disposition
            #                 ):
            #                     existing_history += (
            #                         part.get_payload(decode=True).decode("UTF-8") + "\n"
            #                     )
            #         else:
            #             existing_history = thread_msg.get_payload(decode=True).decode(
            #                 "UTF-8"
            #             )

            # # Append the content of the latest email to the history
            # if existing_history:
            #     email_content = (
            #         existing_history + "\n\nLatest email:\n\n" + email_content
            #     )

            message = MIMEText(
                openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are Beta AI, an AI assistant for managing emails. Your email address is ai.beta.dev@gmail.com. You are sent an email thread where you are potentially given the email history, certainly followed by the email the sender just sent. Write the email body that would be sent back to the sender. Limit prose.",
                        },
                        {"role": "user", "content": email_content},
                    ],
                )
                .choices[0]
                .message.content
            )
            message["From"] = EMAIL_ACCOUNT
            message["To"] = from_email
            message["Subject"] = reply_subject

            if thread_id:
                message.add_header("In-Reply-To", thread_id)
                message.add_header("References", thread_id)

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.starttls()
                smtp.login(EMAIL_ACCOUNT, PASSWORD)
                smtp.sendmail(EMAIL_ACCOUNT, from_email, message.as_string())
                print(f"Replied to {from_email}")

            # Mark the email as seen
            mail.store(email_id, "+FLAGS", "\\Seen")
    except Exception as e:
        print(f"Failed to process email ID {email_id}: {e}")
        raise (e)


# Connect to the IMAP server and log in
mail = imaplib.IMAP4_SSL(IMAP_SERVER)
mail.login(EMAIL_ACCOUNT, PASSWORD)
# mail.select('inbox')

# Continuously check for new emails and reply
try:
    while True:
        # Search for all unseen emails
        mail.select("inbox")
        result, data = mail.search(None, "UNSEEN")
        if result == "OK" and data[0]:
            for num in data[0].split():
                auto_reply(mail, num)
            print("Waiting for new emails...")
        # else:
        #     print("No new unseen emails.")
        time.sleep(0.5)  # Check every 60 seconds
except Exception as e:
    print("Error:", e)
finally:
    mail.logout()
