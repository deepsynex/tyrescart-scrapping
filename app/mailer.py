import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

try:
    from dotenv import load_dotenv
    # Load .env from project root if present
    _env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.isfile(_env_path):
        load_dotenv(_env_path)
    else:
        load_dotenv()
except Exception:
    pass

# Gmail SMTP configuration -- reads from .env with fallback defaults
GMAIL_USER = os.environ.get('GMAIL_USER', 'task.klever@gmail.com')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', 'mschrzdtlqdxykoo')
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT_SSL = int(os.environ.get('SMTP_PORT_SSL', '465'))
SMTP_PORT_TLS = int(os.environ.get('SMTP_PORT_TLS', '587'))
MAIL_FROM = os.environ.get('MAIL_FROM', GMAIL_USER)
OWNER_EMAIL = os.environ.get('OWNER_EMAIL') or os.environ.get('TO_OWNER_EMAIL')



def send_email(to_address, subject, html_body, text_body=None, inline_images=None):
    """
    Sends an HTML email via Gmail SMTP with dual SSL 465 and TLS 587 support.
    Supports inline CID images (e.g. {'tyresvision_logo': 'path/to/logo.png'})
    for bulletproof cross-client image rendering without external image blocking.
    """
    if inline_images:
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = to_address

        msg_alt = MIMEMultipart('alternative')
        msg.attach(msg_alt)

        if text_body:
            msg_alt.attach(MIMEText(text_body, 'plain', 'utf-8'))
        if html_body:
            msg_alt.attach(MIMEText(html_body, 'html', 'utf-8'))

        for cid_name, img_path in inline_images.items():
            if img_path and os.path.isfile(img_path):
                try:
                    with open(img_path, 'rb') as f:
                        img_data = f.read()
                    mime_img = MIMEImage(img_data)
                    mime_img.add_header('Content-ID', f'<{cid_name}>')
                    mime_img.add_header('Content-Disposition', 'inline', filename=os.path.basename(img_path))
                    msg.attach(mime_img)
                except Exception as img_err:
                    print(f"Warning: Failed to attach inline image {cid_name}: {img_err}")
    else:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = to_address

        if text_body:
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    errors = []

    # 1. Primary: Direct SSL on port 465
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT_SSL, timeout=20) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            return True
    except Exception as e:
        errors.append(f'SSL 465 failed: {e}')

    # 2. Fallback: STARTTLS on port 587
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT_TLS, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
            return True
    except Exception as e:
        errors.append(f'TLS 587 failed: {e}')

    raise RuntimeError(f"Failed to send email via Gmail SMTP: {'; '.join(errors)}")