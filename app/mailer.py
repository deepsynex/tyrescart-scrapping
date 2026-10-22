import os
import re
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

# SMTP configuration. SMTP_USER/SMTP_PASS/SMTP_FROM are the current names;
# the GMAIL_* names are still honoured so an older .env keeps working.
SMTP_USER = (os.environ.get('SMTP_USER')
             or os.environ.get('GMAIL_USER', 'info@tyrescart.ae'))
SMTP_PASS = (os.environ.get('SMTP_PASS')
             or os.environ.get('GMAIL_APP_PASSWORD', ''))
SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.office365.com')
SMTP_FROM = (os.environ.get('SMTP_FROM')
             or os.environ.get('MAIL_FROM')
             or SMTP_USER)

# 'tls' = STARTTLS on 587 (Office 365), 'ssl' = implicit TLS on 465 (Gmail).
SMTP_ENCRYPTION = (os.environ.get('SMTP_ENCRYPTION') or 'tls').strip().lower()
_default_port = '465' if SMTP_ENCRYPTION == 'ssl' else '587'
SMTP_PORT = int(os.environ.get('SMTP_PORT', _default_port))
SMTP_PORT_SSL = int(os.environ.get('SMTP_PORT_SSL', '465'))
SMTP_PORT_TLS = int(os.environ.get('SMTP_PORT_TLS', '587'))

# Address(es) copied on every outgoing message. Comma/semicolon separated.
MAIL_CC = os.environ.get('MAIL_CC', '')

# Back-compat aliases -- several modules import these names directly.
GMAIL_USER = SMTP_USER
GMAIL_APP_PASSWORD = SMTP_PASS
MAIL_FROM = SMTP_FROM
OWNER_EMAIL = os.environ.get('OWNER_EMAIL') or os.environ.get('TO_OWNER_EMAIL')


def _addr_list(raw):
    """Splits a comma/semicolon separated address string or handles lists/tuples into clean RFC-compliant email addresses."""
    if not raw:
        return []
    if isinstance(raw, (list, tuple, set)):
        items = raw
    else:
        items = re.split(r'[,;]', str(raw))

    clean = []
    for item in items:
        for part in re.split(r'[,;]', str(item)):
            cleaned = part.strip().strip("[]'\"<>")
            if cleaned and '@' in cleaned and cleaned not in clean:
                clean.append(cleaned)
    return clean

# Every email template in the database renders its header/footer logo as
# <img src="cid:tyresvision_logo">, which only resolves if the image is attached
# to the message. Callers used to have to remember to pass it themselves, and
# most did not -- so the logo is resolved here instead and attached automatically
# whenever the HTML asks for a CID this map knows about (see _auto_inline_images).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INLINE_IMAGES = {
    'tyresvision_logo': os.path.join(
        _PROJECT_ROOT, 'static', 'assets', 'images', 'logo', 'tyresvision-logo-white.png'),
}


def _auto_inline_images(html_body):
    """Returns the {cid: path} pairs this HTML actually references and that exist
    on disk. Prefers .png over .webp for 100% universal email client compatibility (Gmail, Outlook, Apple Mail)."""
    if not html_body:
        return None
    found = {}
    for cid, path in DEFAULT_INLINE_IMAGES.items():
        if f'cid:{cid}' in html_body:
            base, _ = os.path.splitext(path)
            png_cand = base + '.png'
            if os.path.isfile(png_cand):
                found[cid] = png_cand
            elif os.path.isfile(path):
                found[cid] = path
    return found or None


def send_email(to_address, subject, html_body, text_body=None, inline_images=None, cc=None):
    """
    Sends an HTML email over SMTP, using STARTTLS or implicit SSL according to
    SMTP_ENCRYPTION, and falling back to the other transport if the first fails.
    Supports inline CID images (e.g. {'tyresvision_logo': 'path/to/logo.webp'})
    for bulletproof cross-client image rendering without external image blocking.

    Callers that pass nothing still get the standard brand logo attached when the
    template references it, and MAIL_CC is copied automatically; pass
    inline_images or cc explicitly to override.
    """
    if inline_images is None:
        inline_images = _auto_inline_images(html_body)

    to_list = _addr_list(to_address)
    to_clean = to_list[0] if to_list else str(to_address).strip().strip("[]'\"<>")
    if not to_clean or '@' not in to_clean:
        raise ValueError(f"Invalid recipient email address: {to_address!r}")

    # Only copy CC when explicitly passed (e.g. for customer enquiries).
    # Account-level emails (password resets, welcome invites) send ONLY to to_address.
    cc_list = _addr_list(cc) if cc else []
    # Never copy someone who is already the primary recipient.
    cc_list = [a for a in cc_list if a.lower() != to_clean.lower() and '@' in a]

    all_recipients = [to_clean] + cc_list

    if inline_images:
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        # Office 365 rejects a From that is not the authenticated mailbox.
        msg['From'] = SMTP_FROM
        msg['To'] = to_clean
        if cc_list:
            msg['Cc'] = ', '.join(cc_list)

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
                    ext = os.path.splitext(img_path)[1].lower().lstrip('.')
                    subtype = 'png' if ext == 'png' else ('jpeg' if ext in ('jpg', 'jpeg') else ext)
                    mime_img = MIMEImage(img_data, _subtype=subtype)
                    mime_img.add_header('Content-ID', f'<{cid_name}>')
                    mime_img.add_header('Content-Disposition', 'inline', filename=os.path.basename(img_path))
                    msg.attach(mime_img)
                except Exception as img_err:
                    print(f"Warning: Failed to attach inline image {cid_name}: {img_err}")
    else:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        # Office 365 rejects a From that is not the authenticated mailbox.
        msg['From'] = SMTP_FROM
        msg['To'] = to_clean
        if cc_list:
            msg['Cc'] = ', '.join(cc_list)

        if text_body:
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    errors = []

    def _send_starttls(port):
        with smtplib.SMTP(SMTP_HOST, port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg, from_addr=SMTP_FROM, to_addrs=all_recipients)
        return True

    def _send_ssl(port):
        with smtplib.SMTP_SSL(SMTP_HOST, port, timeout=20) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg, from_addr=SMTP_FROM, to_addrs=all_recipients)
        return True

    # Try the configured transport first. Office 365 only speaks STARTTLS on
    # 587, so leading with implicit SSL would stall for the full timeout on
    # every message before falling through.
    if SMTP_ENCRYPTION == 'ssl':
        attempts = [('SSL', SMTP_PORT, _send_ssl),
                    ('STARTTLS', SMTP_PORT_TLS, _send_starttls)]
    else:
        attempts = [('STARTTLS', SMTP_PORT, _send_starttls),
                    ('SSL', SMTP_PORT_SSL, _send_ssl)]

    for label, port, fn in attempts:
        try:
            return fn(port)
        except Exception as e:
            errors.append(f'{label} {SMTP_HOST}:{port} failed: {e}')

    raise RuntimeError(f"Failed to send email via SMTP: {'; '.join(errors)}")
