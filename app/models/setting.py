import json
from db import get_connection

DEFAULT_COMPANY_INFO = {
    "company_name": "TyresVision",
    "phone_number": "+971 50 506 9575",
    "phone_call_number": "+971505069575",
    "whatsapp_number": "971505069575",
    "whatsapp_display_number": "+971 50 506 9575",
    "email": "support@tyresvision.com",
    "address": "Dubai, United Arab Emirates",
    "working_hours": "Mon - Sat: 8:00 AM - 8:00 PM"
}

DEFAULT_REVIEWER_SETTINGS = {
    "enabled": True,
    "name": {
        "en": "Sharvil Kumar",
        "ar": "شارفيل كومار"
    },
    "initials": "SK",
    "role": {
        "en": "Tyre Selection Specialist, TyresVision",
        "ar": "أخصائي اختيار الإطارات، تايرز فيجن"
    },
    "bio": {
        "en": "Sharvil Kumar oversees operations at TyresVision, helping customers find tyres that match their vehicle and budget. He ensures a smooth purchasing experience and trusted installation support.",
        "ar": "يشرف شارفيل كومار على العمليات في تايرز فيجن، لمساعدة العملاء في العثور على الإطارات المثالية التي تتطابق مع سياراتهم وميزانيتهم، مع ضمان تجربة شراء سلسة وخدمة تركيب معتمدة وموثوقة."
    }
}

class Setting:
    TABLE = "settings"

    @staticmethod
    def _parse_val(raw):
        if raw is None:
            return None
        if isinstance(raw, (dict, list)):
            return raw
        if isinstance(raw, str):
            s = raw.strip()
            if s.startswith("{") or s.startswith("["):
                try:
                    return json.loads(s)
                except Exception:
                    pass
            return raw
        return raw

    @staticmethod
    def _dump_val(val):
        if val is None:
            return None
        if isinstance(val, (dict, list)):
            return json.dumps(val, ensure_ascii=False)
        return str(val)

    @classmethod
    def get(cls, key: str, default=None):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT value FROM settings WHERE `key` = %s LIMIT 1", (key,))
                row = cursor.fetchone()
                if not row or row.get("value") is None:
                    return default
                return cls._parse_val(row.get("value"))
        finally:
            conn.close()

    @classmethod
    def set(cls, key: str, value, group: str = "general") -> bool:
        dumped = cls._dump_val(value)
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO settings (`key`, `value`, `group`, created_at, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON DUPLICATE KEY UPDATE
                        `value` = VALUES(`value`),
                        `group` = VALUES(`group`),
                        updated_at = CURRENT_TIMESTAMP
                """
                cursor.execute(sql, (key, dumped, group))
                conn.commit()
                return True
        finally:
            conn.close()

    @classmethod
    def get_reviewer_settings(cls, locale: str = None) -> dict:
        data = cls.get("reviewer_settings", DEFAULT_REVIEWER_SETTINGS)
        if not isinstance(data, dict):
            data = DEFAULT_REVIEWER_SETTINGS.copy()

        enabled_val = data.get("enabled", True)
        if isinstance(enabled_val, str):
            enabled = enabled_val.strip().lower() in ("true", "1", "yes")
        else:
            enabled = bool(enabled_val)

        name_val = data.get("name") or DEFAULT_REVIEWER_SETTINGS["name"]
        initials = str(data.get("initials") or DEFAULT_REVIEWER_SETTINGS["initials"]).strip()
        role_val = data.get("role") or DEFAULT_REVIEWER_SETTINGS["role"]
        bio_val = data.get("bio") or data.get("description") or DEFAULT_REVIEWER_SETTINGS["bio"]

        if locale:
            name_str = (name_val.get(locale) or name_val.get("en") or next(iter(name_val.values()), "")) if isinstance(name_val, dict) else str(name_val)
            role_str = (role_val.get(locale) or role_val.get("en") or next(iter(role_val.values()), "")) if isinstance(role_val, dict) else str(role_val)
            bio_str = (bio_val.get(locale) or bio_val.get("en") or next(iter(bio_val.values()), "")) if isinstance(bio_val, dict) else str(bio_val)

            return {
                "enabled": enabled,
                "name": name_str,
                "initials": initials,
                "role": role_str,
                "bio": bio_str
            }

        return {
            "enabled": enabled,
            "name": name_val if isinstance(name_val, dict) else {"en": str(name_val), "ar": str(name_val)},
            "initials": initials,
            "role": role_val if isinstance(role_val, dict) else {"en": str(role_val), "ar": str(role_val)},
            "bio": bio_val if isinstance(bio_val, dict) else {"en": str(bio_val), "ar": str(bio_val)}
        }

    @classmethod
    def get_company_info(cls) -> dict:
        import re
        data = cls.get("company_info", DEFAULT_COMPANY_INFO)
        if not isinstance(data, dict):
            data = DEFAULT_COMPANY_INFO.copy()

        company_name = str(data.get("company_name") or DEFAULT_COMPANY_INFO["company_name"]).strip()
        phone_number = str(data.get("phone_number") or DEFAULT_COMPANY_INFO["phone_number"]).strip()
        raw_call = str(data.get("phone_call_number") or phone_number or DEFAULT_COMPANY_INFO["phone_call_number"]).strip()
        phone_call_number = ("+" if raw_call.startswith("+") else "") + re.sub(r"[^\d]", "", raw_call)
        if not phone_call_number:
            phone_call_number = "+971505069575"

        raw_wa = str(data.get("whatsapp_number") or DEFAULT_COMPANY_INFO["whatsapp_number"]).strip()
        whatsapp_number = re.sub(r"[^\d]", "", raw_wa)
        if not whatsapp_number:
            whatsapp_number = "971505069575"

        whatsapp_display = str(data.get("whatsapp_display_number") or f"+{whatsapp_number}").strip()
        email = str(data.get("email") or DEFAULT_COMPANY_INFO["email"]).strip()
        address = str(data.get("address") or DEFAULT_COMPANY_INFO["address"]).strip()
        working_hours = str(data.get("working_hours") or DEFAULT_COMPANY_INFO["working_hours"]).strip()

        return {
            "company_name": company_name,
            "phone_number": phone_number,
            "phone": phone_number,
            "phone_call_number": phone_call_number,
            "phone_call": phone_call_number,
            "whatsapp_number": whatsapp_number,
            "whatsapp": whatsapp_number,
            "whatsapp_display_number": whatsapp_display,
            "whatsapp_display": whatsapp_display,
            "whatsapp_url": f"https://wa.me/{whatsapp_number}",
            "phone_url": f"tel:{phone_call_number}",
            "email": email,
            "address": address,
            "working_hours": working_hours,
        }

    @classmethod
    def set_company_info(cls, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        existing = cls.get("company_info", DEFAULT_COMPANY_INFO)
        if not isinstance(existing, dict):
            existing = DEFAULT_COMPANY_INFO.copy()
        clean_data = {
            "company_name": str(payload.get("company_name") or existing.get("company_name") or "TyresVision").strip(),
            "phone_number": str(payload.get("phone_number") or existing.get("phone_number") or "+971 50 506 9575").strip(),
            "phone_call_number": str(payload.get("phone_call_number") or existing.get("phone_call_number") or "+971505069575").strip(),
            "whatsapp_number": str(payload.get("whatsapp_number") or existing.get("whatsapp_number") or "971505069575").strip(),
            "whatsapp_display_number": str(payload.get("whatsapp_display_number") or existing.get("whatsapp_display_number") or "+971 50 506 9575").strip(),
            "email": str(payload.get("email") or existing.get("email") or "support@tyresvision.com").strip(),
            "address": str(payload.get("address") or existing.get("address") or "Dubai, United Arab Emirates").strip(),
            "working_hours": str(payload.get("working_hours") or existing.get("working_hours") or "Mon - Sat: 8:00 AM - 8:00 PM").strip()
        }
        return cls.set("company_info", clean_data, group="company")
