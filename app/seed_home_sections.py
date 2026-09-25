import json
import sys
sys.path.insert(0, 'app')
from db import get_connection
from models.page_section import PageSection

HOME_SECTIONS = [
    # 1. HERO SECTION
    {
        "page_slug": "home",
        "section_type": "hero",
        "section_subtitle": {
            "en": "Dubai · Abu Dhabi · Sharjah · Ajman",
            "ar": "دبي · أبوظبي · الشارقة · عجمان"
        },
        "section_title": {
            "en": "Buy tyres online.\n<em>Fitted locally</em> across the UAE.",
            "ar": "اشترِ الإطارات عبر الإنترنت.\n<em>تركيب محلي</em> في جميع أنحاء الإمارات."
        },
        "content": {
            "en": "TyresVision is an online tyre shop for the UAE. Genuine, date-fresh tyres from 60+ brands at the lowest prices — delivered free to a fitting centre near you, or fitted at your home or office by our mobile vans.",
            "ar": "تايرز فيجن هو متجر إطارات إلكتروني رائد في الإمارات. إطارات أصلية وتواريخ إنتاج حديثة من أكثر من 60 علامة تجارية بأقل الأسعار — توصيل مجاني إلى مركز تركيب قريب منك، أو تركيب متنقل عند باب منزلك أو مكتبك."
        },
        "button_text": {
            "en": "WhatsApp for a quote",
            "ar": "اطلب عرض سعر عبر واتساب"
        },
        "button_url": "https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.",
        "section_data": {
            "phone": "+971505069575",
            "phone_display": "+971 50 506 9575",
            "badges": [
                {"icon": "dollar", "text": {"en": "Lowest price guaranteed", "ar": "أقل سعر مضمون"}},
                {"icon": "shield", "text": {"en": "Warranty on eligible tyres", "ar": "ضمان على الإطارات المؤهلة"}},
                {"icon": "truck", "text": {"en": "Free delivery to fitter", "ar": "توصيل مجاني لمركز التركيب"}}
            ],
            "quote_card": {
                "title": {"en": "Get your tyre price in minutes", "ar": "احصل على سعر إطاراتك في دقائق"},
                "subtitle": {"en": "Send us your size — we’ll reply on WhatsApp with options and prices.", "ar": "أرسل لنا مقاس إطاراتك — وسنرد عليك عبر واتساب بالخيارات والأسعار."},
                "button_text": {"en": "Send on WhatsApp", "ar": "إرسال عبر واتساب"},
                "note": {"en": "Opens WhatsApp with your details pre-filled. No account needed.", "ar": "يفتح واتساب مع ملء بياناتك مسبقاً. لا يلزم إنشاء حساب."}
            }
        },
        "sort_order": 1,
        "is_active": 1
    },

    # 2. STATS SECTION
    {
        "page_slug": "home",
        "section_type": "stats",
        "section_title": {
            "en": "Key Numbers",
            "ar": "أرقامنا المميزة"
        },
        "section_data": {
            "metrics": [
                {"number": "60+", "label": {"en": "Tyre brands", "ar": "علامة تجارية للإطارات"}, "icon": "brand"},
                {"number": "7,000+", "label": {"en": "Products in stock", "ar": "منتج متوفر في المخزون"}, "icon": "tyre"},
                {"number": "25+", "label": {"en": "Fitting locations", "ar": "موقع تركيب معتمد"}, "icon": "globe"},
                {"number": "10+", "label": {"en": "Mobile Van Fitting", "ar": "فانات تركيب متنقلة"}, "icon": "truck"}
            ]
        },
        "sort_order": 2,
        "is_active": 1
    },

    # 3. WHY / FEATURES SECTION
    {
        "page_slug": "home",
        "section_type": "features",
        "section_subtitle": {
            "en": "Why TyresVision?",
            "ar": "لماذا تايرز فيجن؟"
        },
        "section_title": {
            "en": "Everything a tyre shop should be — without the runaround",
            "ar": "كل ما يجب أن يقدمه متجر الإطارات — بدون تعقيدات"
        },
        "content": {
            "en": "No haggling, no upselling, no waiting around. Pick your tyres, pick where you want them fitted, and get on with your day.",
            "ar": "لا مساومة، لا بيع عشوائي، لا انتظار. اختر إطاراتك، وحدد موقع التركيب، وتابع يومك براحة تامة."
        },
        "section_data": {
            "cards": [
                {
                    "icon": "shield",
                    "title": {"en": "Genuine tyres only", "ar": "إطارات أصلية 100%"},
                    "description": {"en": "Sourced through authorised channels with manufacturer-backed warranty on eligible tyres. Fresh manufacturing dates — never old stock.", "ar": "مستوردة عبر القنوات الرسمية المعتمدة مع ضمان الشركة المصنعة على الإطارات المؤهلة. تواريخ إنتاج حديثة — خالية تماماً من المخزون القديم."}
                },
                {
                    "icon": "dollar",
                    "title": {"en": "Lowest price, guaranteed", "ar": "أفضل وأقل سعر مضمون"},
                    "description": {"en": "Found the same tyre cheaper elsewhere in the UAE? Send us the quote on WhatsApp and we’ll match or beat it.", "ar": "هل وجدت نفس الإطار بسعر أرخص في الإمارات؟ أرسل لنا عرض السعر على واتساب وسنطابقه أو نمنحك سعراً أفضل."}
                },
                {
                    "icon": "truck",
                    "title": {"en": "We come to you", "ar": "نصل إليك أينما كنت"},
                    "description": {"en": "Mobile fitting vans across the UAE will change your tyres at home, at the office, or in the mall car park while you’re inside.", "ar": "فانات التركيب المتنقل في جميع أنحاء الإمارات تقوم بتبديل إطاراتك في المنزل، في المكتب، أو في مواقف المول أثناء تسوقك."}
                },
                {
                    "icon": "clock",
                    "title": {"en": "Fast turnaround", "ar": "سرعة استجابة وتركيب فوري"},
                    "description": {"en": "Most popular sizes are in stock and ready to go, so fitting can usually be arranged within the same day across Dubai and Sharjah.", "ar": "معظم المقاسات الشائعة متوفرة في المخزون وجاهزة، مما يتيح ترتيب التركيب في نفس اليوم عبر دبي والشارقة."}
                },
                {
                    "icon": "award",
                    "title": {"en": "Warranty handled for you", "ar": "إدارة الضمان بالكامل"},
                    "description": {"en": "Every purchase is logged against your vehicle, so warranty questions and claims come to us — no chasing the manufacturer yourself.", "ar": "يتم تسجيل كل عملية شراء برقم مركبتك، لنتولى نحن كافة إجراءات ومطالبات الضمان نيابة عنك."}
                },
                {
                    "icon": "zap",
                    "title": {"en": "Built for UAE roads", "ar": "مصممة لطرقات الإمارات"},
                    "description": {"en": "Advice tuned to Gulf heat and long highway runs — the right compound and load rating for how you actually drive.", "ar": "نصائح وإطارات ملائمة لحرارة الخليج والطرق السريعة — المركب المناسب ومعدل الحمولة المتوافق مع قيادتك."}
                }
            ],
            "cta_row": {
                "wa_text": {"en": "Chat on WhatsApp", "ar": "تحدث معنا عبر واتساب"},
                "wa_url": "https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.",
                "call_text": {"en": "Call +971 50 506 9575", "ar": "اتصل بنا: 9575 506 50 971+"},
                "call_url": "tel:+971505069575"
            }
        },
        "sort_order": 3,
        "is_active": 1
    },

    # 4. SERVICES SECTION
    {
        "page_slug": "home",
        "section_type": "services",
        "section_subtitle": {
            "en": "Full car care",
            "ar": "عناية متكاملة بسيارتك"
        },
        "section_title": {
            "en": "More than tyres",
            "ar": "أكثر من مجرد إطارات"
        },
        "content": {
            "en": "Book any of these alongside your tyre fitting and save a second trip.",
            "ar": "احجز أي من هذه الخدمات الإضافية مع تركيب الإطارات ووفر على نفسك وقتاً وزيارة إضافية."
        },
        "section_data": {
            "services": [
                {"name": {"en": "Tyre fitting", "ar": "تركيب الإطارات"}},
                {"name": {"en": "Wheel alignment", "ar": "ميزان الإطارات (محاذاة)"}},
                {"name": {"en": "Wheel balancing", "ar": "ترصيص العجلات"}},
                {"name": {"en": "Tyre rotation", "ar": "تدوير الإطارات"}},
                {"name": {"en": "Nitrogen fill", "ar": "تعبئة غاز النيتروجين"}},
                {"name": {"en": "Car batteries", "ar": "بطاريات السيارات"}},
                {"name": {"en": "Oil change", "ar": "تغيير الزيت والفلاتر"}},
                {"name": {"en": "AC repair", "ar": "صيانة وتعبئة مكيف السيارة"}},
                {"name": {"en": "Service & repair", "ar": "الصيانة الميكانيكية العامة"}},
                {"name": {"en": "Car spa & detailing", "ar": "تلميع وتنظيف شامل (سبا)"}},
                {"name": {"en": "Window tinting", "ar": "تظليل وتعتيم النوافذ"}},
                {"name": {"en": "Car recovery", "ar": "خدمة ونش وسطحة الإنقاذ"}},
                {"name": {"en": "Car insurance", "ar": "تأمين المركبات"}},
                {"name": {"en": "Puncture repair", "ar": "إصلاح البنشر والثقوب"}},
                {"name": {"en": "Fleet servicing", "ar": "خدمة وصيانة أساطيل الشركات"}},
                {"name": {"en": "Mobile van visit", "ar": "زيارة الفان المتنقل"}}
            ]
        },
        "sort_order": 4,
        "is_active": 1
    },

    # 5. HOW IT WORKS SECTION
    {
        "page_slug": "home",
        "section_type": "how_it_works",
        "section_subtitle": {
            "en": "How it works",
            "ar": "كيف تعمل الخدمة"
        },
        "section_title": {
            "en": "Four steps, one afternoon",
            "ar": "أربع خطوات بسيطة في وقت قياسي"
        },
        "section_data": {
            "steps": [
                {
                    "step_number": 1,
                    "icon": "phone",
                    "title": {"en": "Send your size", "ar": "أرسل مقاس إطارك"},
                    "description": {"en": "WhatsApp us the numbers on your tyre sidewall, or just your car model and year.", "ar": "راسلنا على واتساب بالأرقام المكتوبة على جدار إطارك أو فقط موديل وسنة سيارتك."}
                },
                {
                    "step_number": 2,
                    "icon": "dollar",
                    "title": {"en": "Get options & prices", "ar": "استلم الخيارات والأسعار"},
                    "description": {"en": "We reply with best-value, mid-range and premium options — all in stock.", "ar": "نرد عليك بأفضل الخيارات الاقتصادية، المتوسطة، والممتازة — جميعها متوفرة فوراً."}
                },
                {
                    "step_number": 3,
                    "icon": "globe",
                    "title": {"en": "Pick your fitter", "ar": "اختر طريقة ومكان التركيب"},
                    "description": {"en": "Choose a centre near you, or book a mobile van to your address.", "ar": "اختر مركز تركيب معتمد قريب منك، أو اطلب فان الخدمة المتنقلة لعندك."}
                },
                {
                    "step_number": 4,
                    "icon": "truck",
                    "title": {"en": "Drive away", "ar": "انطلق بأمان"},
                    "description": {"en": "Fitting, balancing and disposal of the old tyres are handled. Warranty is logged for you.", "ar": "يتم إنجاز التركيب، الترصيص، والتخلص من الإطارات القديمة، مع تسجيل الضمان رسمياً."}
                }
            ],
            "cta_row": {
                "wa_text": {"en": "Start on WhatsApp", "ar": "ابدأ الآن عبر واتساب"},
                "wa_url": "https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.",
                "call_text": {"en": "Prefer to talk? Call us", "ar": "تفضل الاتصال؟ اتصل بنا مباشرة"},
                "call_url": "tel:+971505069575"
            }
        },
        "sort_order": 5,
        "is_active": 1
    },

    # 6. BRANDS SECTION
    {
        "page_slug": "home",
        "section_type": "brands",
        "section_subtitle": {
            "en": "60+ brands in stock",
            "ar": "+60 علامة تجارية في المخزون"
        },
        "section_title": {
            "en": "The names you trust, the prices you don’t expect",
            "ar": "العلامات التي تثق بها، بالأسعار التي لا تتوقعها"
        },
        "section_data": {
            "brands": [
                "Michelin", "Bridgestone", "Goodyear", "Continental", "Pirelli", "Dunlop",
                "Hankook", "Yokohama", "Toyo", "Falken", "Nexen", "Kumho",
                "BFGoodrich", "Cooper", "Nitto", "Vredestein", "Giti", "Laufenn",
                "Sumitomo", "Zeetex", "+40 more"
            ]
        },
        "sort_order": 6,
        "is_active": 1
    },

    # 7. TESTIMONIALS / REVIEWS SECTION
    {
        "page_slug": "home",
        "section_type": "testimonials",
        "section_subtitle": {
            "en": "Customer reviews",
            "ar": "تقييمات وآراء العملاء"
        },
        "section_title": {
            "en": "What UAE drivers say",
            "ar": "ماذا يقول سائقو الإمارات"
        },
        "section_data": {
            "reviews": [
                {
                    "rating": 5,
                    "quote": {
                        "en": "Sent my tyre size in the morning, had a price back in minutes and the car was done the same afternoon.",
                        "ar": "أرسلت مقاس إطاري صباحاً، وتلقيت السعر في دقائق وتم تركيب الإطارات في نفس بعد الظهر."
                    },
                    "author": {"en": "Verified customer", "ar": "عميل موثوق"},
                    "location": {"en": "Dubai", "ar": "دبي"}
                },
                {
                    "rating": 5,
                    "quote": {
                        "en": "Straight answers, no upselling, and the price was better than the two shops I’d already called.",
                        "ar": "إجابات واضحة ومباشرة بدون محاولات بيع إضافي، وكان السعر أفضل بكثير من المحلين اللذين اتصلت بهما مسبقاً."
                    },
                    "author": {"en": "Verified customer", "ar": "عميل موثوق"},
                    "location": {"en": "Sharjah", "ar": "الشارقة"}
                },
                {
                    "rating": 5,
                    "quote": {
                        "en": "The mobile van came to my building’s car park. I didn’t have to take time off work at all.",
                        "ar": "وصل الفان المتنقل إلى موقف بنايتي. لم أضطر لأخذ إجازة أو مغادرة العمل على الإطلاق."
                    },
                    "author": {"en": "Verified customer", "ar": "عميل موثوق"},
                    "location": {"en": "Abu Dhabi", "ar": "أبوظبي"}
                }
            ]
        },
        "sort_order": 7,
        "is_active": 1
    },

    # 8. FAQ SECTION
    {
        "page_slug": "home",
        "section_type": "faq",
        "section_subtitle": {
            "en": "Questions",
            "ar": "الأسئلة الشائعة"
        },
        "section_title": {
            "en": "Good to know",
            "ar": "معلومات تهمك"
        },
        "section_data": {
            "faqs": [
                {
                    "question": {
                        "en": "How do I find my tyre size?",
                        "ar": "كيف أجد مقاس إطاري؟"
                    },
                    "answer": {
                        "en": "It’s printed on the sidewall of your current tyre — something like <strong>235/55 R19 105W</strong>. Send a photo on WhatsApp if you’re not sure, or share your car’s make, model and year and TyresVision will look it up.",
                        "ar": "ستجده مطبوعاً على جدار إطارك الحالي — مثل <strong>235/55 R19 105W</strong>. يمكنك إرسال صورة عبر واتساب أو تزويدنا بموديل وسنة سيارتك لنقوم بتحديده لك."
                    }
                },
                {
                    "question": {
                        "en": "Is fitting included in the price?",
                        "ar": "هل التركيب مشمول في السعر؟"
                    },
                    "answer": {
                        "en": "Delivery to your chosen fitting centre is free and fitting is arranged for you. Mobile fitting at your own location and extras such as alignment are quoted upfront — no surprises at the till.",
                        "ar": "التوصيل والتركيب في مركز الشريك المعتمد مشمول ومجاني. أما التركيب المتنقل والخدمات الإضافية كالترصيص فيتم تحديد أسعارها بوضوح مسبقاً."
                    }
                },
                {
                    "question": {
                        "en": "Are the tyres new and date-fresh?",
                        "ar": "هل الإطارات جديدة وتاريخ إنتاجها حديث؟"
                    },
                    "answer": {
                        "en": "Yes. Every tyre is brand new with a recent manufacturing date, sourced through authorised channels, and eligible tyres carry manufacturer-backed warranty.",
                        "ar": "نعم. كل إطار جديد تماماً ومرفق بتاريخ إنتاج حديث، ومستورد عبر الوكلاء الرسميين مع ضمان المصنع."
                    }
                },
                {
                    "question": {
                        "en": "Which emirates does TyresVision cover?",
                        "ar": "ما هي الإمارات التي تغطيها تايرز فيجن؟"
                    },
                    "answer": {
                        "en": "Dubai, Abu Dhabi, Sharjah, Ajman and the rest of the UAE, through a network of fitting centres and mobile vans.",
                        "ar": "دبي، أبوظبي، الشارقة، عجمان وكافة إمارات الدولة عبر شبكة واسعة من مراكز الخدمة والفانات المتنقلة."
                    }
                },
                {
                    "question": {
                        "en": "Can TyresVision handle a company fleet?",
                        "ar": "هل توفرون خدمات لأساطيل الشركات؟"
                    },
                    "answer": {
                        "en": "Yes — fleet pricing, consolidated invoicing and scheduled on-site visits are available. Call and ask for the fleet desk.",
                        "ar": "نعم — نوفر أسعاراً مخصصة للأساطيل، فواتير موحدة، وزيارات صيانة مجدولة في موقعك. تواصل مع قسم الأساطيل."
                    }
                },
                {
                    "question": {
                        "en": "What if I need help right now?",
                        "ar": "ماذا لو احتجت للمساعدة فوراً؟"
                    },
                    "answer": {
                        "en": "Message TyresVision on WhatsApp at <a href=\"https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.\" target=\"_blank\">+971 50 506 9575</a> or call the same number.",
                        "ar": "راسل تايرز فيجن على واتساب على الرقم <a href=\"https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.\" target=\"_blank\">9575 506 50 971+</a> أو اتصل على نفس الرقم."
                    }
                }
            ]
        },
        "sort_order": 8,
        "is_active": 1
    },

    # 9. FINAL CTA SECTION
    {
        "page_slug": "home",
        "section_type": "cta",
        "section_title": {
            "en": "Ready for a fresh set of tyres?",
            "ar": "هل أنت مستعد لتبديل إطاراتك بأحدث الموديلات؟"
        },
        "content": {
            "en": "Send your tyre size on WhatsApp for a price in minutes — or call and we’ll sort it out on the phone.",
            "ar": "أرسل مقاس إطاراتك عبر واتساب للحصول على أفضل سعر في دقائق — أو اتصل بنا وسنرتب كل شيء عبر الهاتف."
        },
        "button_text": {
            "en": "WhatsApp us",
            "ar": "راسلنا على واتساب"
        },
        "button_url": "https://wa.me/971505069575?text=Hi%20Online%20Tyres%20Shop%2C%20I%27d%20like%20a%20tyre%20quote.",
        "section_data": {
            "call_button_text": {"en": "Call +971 50 506 9575", "ar": "اتصل بنا: 9575 506 50 971+"},
            "call_button_url": "tel:+971505069575",
            "footer_note": {
                "en": "Open daily — call or message any time and we’ll come back to you fast.",
                "ar": "مفتوح يومياً — اتصل أو راسلنا في أي وقت وسنرد عليك بسرعة فائقة."
            }
        },
        "sort_order": 9,
        "is_active": 1
    }
]

def seed_home_sections():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM page_sections WHERE page_slug = 'home' AND deleted_at IS NULL")
            res = cursor.fetchone()
            cnt = res['cnt'] if isinstance(res, dict) else res[0]
            if cnt > 0:
                print(f"Home page sections already exist in DB ({cnt} sections). Cleaning existing home sections before seeding fresh...")
                cursor.execute("DELETE FROM page_sections WHERE page_slug = 'home'")
                conn.commit()

            print("Inserting 9 Home Page Sections into page_sections table...")
            for sec in HOME_SECTIONS:
                PageSection.create(sec)
            print(f"Successfully seeded {len(HOME_SECTIONS)} Home Page sections!")
    finally:
        conn.close()

if __name__ == '__main__':
    seed_home_sections()
