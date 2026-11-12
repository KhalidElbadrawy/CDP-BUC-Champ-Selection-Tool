"""English / Arabic UI strings. English text is the key; untranslated strings fall back to English."""
from __future__ import annotations

import re

from markupsafe import Markup

AR: dict[str, str] = {
    'A story game set at a fictional launch base in the last hour before a launch. You help the crew, handle alerts and make decisions against the clock.': 'لعبة قصصية تدور في قاعدة إطلاق خيالية خلال الساعة الأخيرة قبل الإطلاق. تساعد الطاقم، وتتعامل مع التنبيهات، وتتخذ القرارات في سباق مع الوقت.',
    'You have been shortlisted as a possible CDP Business User Champion. The assessment is a short story game. It looks at how you work with people, keep promises and make decisions under pressure. At the end there are two short questions about your real work. There are no trick questions; act as you really would.': 'تم ترشيحك ضمن القائمة المختصرة لتكون بطلاً لمستخدمي الأعمال في المنصات الرقمية المشتركة. التقييم لعبة قصصية قصيرة، تنظر في طريقة عملك مع الآخرين، ووفائك بالوعود، واتخاذك للقرارات تحت الضغط. وفي النهاية سؤالان قصيران عن عملك الفعلي. لا توجد أسئلة خادعة؛ تصرّف كما تتصرف فعلاً.',
    'Play LAUNCH WINDOW (recommended)': 'العب نافذة الإطلاق (موصى به)',
    'A role-playing game with voices, music and a countdown, in English or Arabic. Captions are always on.': 'لعبة أدوار بأصوات وموسيقى وعدّ تنازلي، بالعربية أو الإنجليزية. الترجمة النصية تظهر دائماً.',
    'About 35 minutes plus two short questions, with a few timed moments.': 'نحو 35 دقيقة وسؤالان قصيران، مع بعض اللحظات المحددة بوقت.',
    'Best on a laptop or tablet with sound. Your progress is saved after every move.': 'الأفضل على حاسوب محمول أو جهاز لوحي مع الصوت. يُحفظ تقدّمك بعد كل خطوة.',
    'Play LAUNCH WINDOW': 'العب نافذة الإطلاق',
    'The same launch-base situations, answered in writing.': 'المواقف نفسها في قاعدة الإطلاق، بإجابات مكتوبة.',
    'The written scenarios': 'المواقف المكتوبة',
    "CDP Champion Nomination Tool": "أداة ترشيح أبطال المنصات الرقمية المشتركة",
    "Common Digital Platforms": "المنصات الرقمية المشتركة",
    "Business User Champion": "بطل مستخدمي الأعمال",
    "Become a CDP Business User Champion": "كن بطلاً لمستخدمي الأعمال في المنصات الرقمية المشتركة",
    "Role information": "معلومات الدور",
    "What champions do": "ما يقوم به الأبطال",
    "Time commitment": "الالتزام الزمني",
    "Benefits": "المزايا",
    "Role boundaries": "حدود الدور",
    "Nominate": "ترشيح",
    "Submit nomination": "إرسال الترشيح",
    "Nomination route": "مسار الترشيح",
    "Self-nomination": "ترشيح ذاتي",
    "Peer nomination": "ترشيح من زميل",
    "Manager nomination": "ترشيح من المدير",
    "Nominee name": "اسم المرشح",
    "Nominee work email": "البريد الإلكتروني للعمل للمرشح",
    "Entity": "الجهة",
    "Department": "الإدارة",
    "Business function": "الوظيفة",
    "Location": "الموقع",
    "Relevant platform": "المنصة ذات الصلة",
    "Business workflow": "إجراء العمل",
    "Your name": "اسمك",
    "Your work email": "بريدك الإلكتروني للعمل",
    "Relationship to nominee": "العلاقة بالمرشح",
    "Brief reason for nomination": "سبب موجز للترشيح",
    "Line-manager name": "اسم المدير المباشر",
    "Line-manager work email": "البريد الإلكتروني للمدير المباشر",
    "Thank you": "شكراً لك",
    "Request a fresh access link": "طلب رابط دخول جديد",
    "Send link": "إرسال الرابط",
    "Work email": "البريد الإلكتروني للعمل",
    "Sign out": "تسجيل الخروج",
    "Status": "الحالة",
    "Next action": "الإجراء التالي",
    "Responsible": "المسؤول",
    "Due": "تاريخ الاستحقاق",
    "Overdue": "متأخر",
    "Save": "حفظ",
    "Save and continue later": "حفظ والمتابعة لاحقاً",
    "Submit application": "إرسال الطلب",
    "Consent": "الموافقة",
    "I consent": "أوافق",
    "I decline": "أرفض",
    "Upload CV": "تحميل السيرة الذاتية",
    "Upload": "تحميل",
    "Extracted information": "المعلومات المستخرجة",
    "Assessment questions": "أسئلة التقييم",
    "Availability": "التوفر",
    "Proposed protected hours per month": "الساعات المحمية المقترحة شهرياً",
    "Your application": "طلبك",
    "Application progress": "تقدم الطلب",
    "Outstanding requests": "الطلبات المعلقة",
    "Assessment outcome": "نتيجة التقييم",
    "Withdraw": "انسحاب",
    "Withdraw from the process": "الانسحاب من العملية",
    "Request reconsideration": "طلب إعادة النظر",
    "Central dashboard": "لوحة المتابعة المركزية",
    "Entity dashboard": "لوحة متابعة الجهة",
    "Nominations": "الترشيحات",
    "Coverage": "التغطية",
    "Target": "المستهدف",
    "Submitted": "مقدم",
    "Send reminder": "إرسال تذكير",
    "Resend link": "إعادة إرسال الرابط",
    "Export register (CSV)": "تصدير السجل (CSV)",
    "Manager commitment": "التزام المدير",
    "Sponsor decision": "قرار الراعي",
    "Protected hours per month": "الساعات المحمية شهرياً",
    "Workload arrangements": "ترتيبات عبء العمل",
    "Required access confirmed": "تم تأكيد الصلاحيات المطلوبة",
    "Outstanding access actions": "إجراءات الصلاحيات المعلقة",
    "Confirm commitment": "تأكيد الالتزام",
    "Decision": "القرار",
    "Rationale": "المبررات",
    "Record decision": "تسجيل القرار",
    "Role acceptance": "قبول الدور",
    "Accept role charter": "قبول ميثاق الدور",
    "Onboarding": "التهيئة",
    "Day-90 review": "مراجعة اليوم التسعين",
    "Demo mode": "وضع العرض التجريبي",
    "AI-generated": "مُنشأ بالذكاء الاصطناعي",
    "SIMULATED": "محاكاة",
    "Settings": "الإعدادات",
    "Entities": "الجهات",
    "Email templates": "قوالب البريد",
    "Outbox": "صندوق الصادر",
    "Audit trail": "سجل التدقيق",
    "Nominated": "مُرشَّح",
    "Awaiting Consent": "بانتظار الموافقة",
    "Application in Progress": "الطلب قيد الإعداد",
    "Awaiting Evidence": "بانتظار أدلة إضافية",
    "Automated Assessment in Progress": "التقييم الآلي جارٍ",
    "Reassessment Required": "إعادة التقييم مطلوبة",
    "Assessment Complete": "اكتمل التقييم",
    "Awaiting Manager Commitment": "بانتظار التزام المدير",
    "Awaiting Sponsor Decision": "بانتظار قرار الراعي",
    "Provisionally Appointed": "معيّن مبدئياً",
    "Awaiting Day-90 Review": "بانتظار مراجعة اليوم التسعين",
    "Confirmed": "مؤكد",
    "Withdrawn": "منسحب",
    "Not Selected": "لم يتم الاختيار",
    "Appointment Concluded": "انتهى التعيين",
    "Link problem": "مشكلة في الرابط",
    "This link has expired.": "انتهت صلاحية هذا الرابط.",
    "This link has been revoked.": "تم إلغاء هذا الرابط.",
    "This link is not valid.": "هذا الرابط غير صالح.",
    "Home": "الرئيسية",
    "Back": "رجوع",
    "Continue": "متابعة",
    "Yes": "نعم",
    "No": "لا",
    "Help colleagues learn approved tasks on the Common Digital Platforms.": "مساعدة الزملاء على تعلم المهام المعتمدة في المنصات الرقمية المشتركة.",
    "Share tips, check understanding and point people to the right guidance.": "مشاركة النصائح والتحقق من الفهم وتوجيه الزملاء إلى الإرشادات الصحيحة.",
    "Log and refer issues (access, defects, policy questions) to the right team.": "تسجيل المشكلات (الصلاحيات، الأعطال، أسئلة السياسات) وإحالتها إلى الفريق المختص.",
    "Give feedback to the CDP Change Team on what users find difficult.": "تقديم الملاحظات لفريق التغيير حول ما يجده المستخدمون صعباً.",
    "Typically 4–8 protected hours a month, agreed with your line manager, plus a short induction.": "عادةً من 4 إلى 8 ساعات محمية شهرياً بالاتفاق مع مديرك المباشر، إضافة إلى برنامج تعريفي قصير.",
    "Early access to platform changes, structured learning, a buddy, and recognition of your contribution.": "اطلاع مبكر على تحديثات المنصات، وتعلم منظم، وزميل مرافق، وتقدير لمساهمتك.",
    "Champions do not grant access, override controls, change policy or replace the service desk. They support, explain and refer.": "لا يمنح الأبطال الصلاحيات ولا يتجاوزون الضوابط ولا يغيرون السياسات ولا يحلون محل مكتب الخدمة؛ بل يدعمون ويشرحون ويحيلون.",
    "Fields marked * are required. The nominee will be asked for consent by email before any CV is collected or any assessment takes place.": "الحقول المعلّمة بـ * إلزامية. سيُطلب من المرشح الموافقة عبر البريد الإلكتروني قبل جمع السيرة الذاتية أو إجراء أي تقييم.",
    "Nominator details (peer or manager nominations)": "بيانات المُرشِّح (ترشيح الزميل أو المدير)",
    "The nomination has been received. The nominee will receive an email asking for their consent before anything further happens.": "تم استلام الترشيح. سيتلقى المرشح بريداً إلكترونياً لطلب موافقته قبل أي إجراء آخر.",
    "Check your email": "تحقق من بريدك الإلكتروني",
    "If this address is linked to the CDP Champion programme, a fresh access link has been emailed to it.": "إذا كان هذا العنوان مرتبطاً ببرنامج الأبطال، فقد أُرسل إليه رابط دخول جديد.",
    'CDP Champion assessment': 'تقييم أبطال المنصات الرقمية المشتركة',
    'Reconnect the City': 'أعِد ربط المدينة',
    'Six districts of the city have lost their connections. As a city champion, your job is to restore reliable services, help districts run on their own, and keep essential safety controls in place.': 'فقدت ست مناطق في المدينة اتصالاتها. بصفتك بطلاً للمدينة، مهمتك استعادة الخدمات بشكل موثوق، ومساعدة المناطق على العمل باستقلالية، والحفاظ على ضوابط السلامة الأساسية.',
    'Before you start': 'قبل أن تبدأ',
    'Hello': 'مرحباً',
    'You have been shortlisted as a possible CDP Business User Champion. This assessment asks how you would handle situations in the NEXUS city. There are no trick questions; answer as you would really act.': 'تم ترشيحك ضمن القائمة المختصرة لتكون بطلاً لمستخدمي الأعمال. يسألك هذا التقييم كيف ستتعامل مع مواقف في مدينة نِكسس. لا توجد أسئلة خادعة؛ أجب كما ستتصرف فعلاً.',
    'Your answers are assessed by AI against a published scorecard, and the CDP Change Lead makes the final decision.': 'تُقيَّم إجاباتك بالذكاء الاصطناعي وفق بطاقة تقييم معلنة، ويتخذ قائد التغيير القرار النهائي.',
    'It takes about 35 to 45 minutes. You can save and come back to this link.': 'يستغرق نحو 35 إلى 45 دقيقة. يمكنك الحفظ والعودة إلى هذا الرابط.',
    'Your answers are seen only by the CDP Change Lead.': 'لا يطّلع على إجاباتك إلا قائد التغيير.',
    'I agree to take part and for my answers to be assessed by AI.': 'أوافق على المشاركة وعلى تقييم إجاباتي بالذكاء الاصطناعي.',
    'Start': 'ابدأ',
    'The city scenarios': 'مواقف المدينة',
    'Answer each scenario in your own words. Specific, practical answers help most.': 'أجب عن كل موقف بكلماتك. الإجابات المحددة والعملية هي الأكثر فائدة.',
    'Your reply': 'ردك',
    'Submit my answers': 'إرسال إجاباتي',
    'After you submit, you may be asked one or two short follow-up questions on this same link.': 'بعد الإرسال، قد يُطلب منك الإجابة عن سؤال أو سؤالين للمتابعة على الرابط نفسه.',
    'A few follow-up questions': 'بعض أسئلة المتابعة',
    'Thank you for your answers. To complete your assessment, please answer these questions.': 'شكراً لإجاباتك. لإكمال تقييمك، يُرجى الإجابة عن هذه الأسئلة.',
    'Question': 'سؤال',
    'Submit': 'إرسال',
    'Your assessment has been submitted. The CDP Change Lead will be in touch about the next steps.': 'تم إرسال تقييمك. سيتواصل معك قائد التغيير بشأن الخطوات التالية.',
    'This assessment link has expired. Please contact the CDP Change Lead for a new link.': 'انتهت صلاحية رابط التقييم. يُرجى التواصل مع قائد التغيير للحصول على رابط جديد.',
    'Credibility and constructive peer influence': 'المصداقية والتأثير البنّاء في الزملاء',
    'Empathy and accessible communication': 'التعاطف والتواصل الميسّر',
    'Reliability and follow-through': 'الموثوقية والمتابعة',
    'Curiosity and learning agility': 'الفضول وسرعة التعلّم',
    'Business workflow capability': 'القدرة على إجراءات العمل',
    'Judgment and evidence quality': 'حسن التقدير وجودة الأدلة',
}


# ----------------------------------------------------------------------------- Change Lead screens
AR.update({
    # layout
    "CDP Champion Selection": "اختيار أبطال المنصات الرقمية المشتركة",
    "Champion Selection": "اختيار الأبطال",
    "Skip to content": "الانتقال إلى المحتوى",
    "Main": "القائمة الرئيسية",
    "Dashboard": "لوحة المتابعة",
    "AI results are <strong>SIMULATED</strong> by a rule-based demo assessor. Add an Anthropic API key for live AI.":
        "نتائج الذكاء الاصطناعي <strong>محاكاة</strong> يُنتجها مقيّم تجريبي قائم على قواعد ثابتة. أضف مفتاح Anthropic API لتفعيل الذكاء الاصطناعي الفعلي.",
    "CDP Change Programme · AI results are provisional. Weights, thresholds and fit categories are proposed settings to calibrate in a pilot.":
        "برنامج التغيير للمنصات الرقمية المشتركة · نتائج الذكاء الاصطناعي مبدئية. الأوزان وحدود القبول وفئات الملاءمة إعدادات مقترحة تُعايَر في مرحلة تجريبية.",
    # sign-in
    "Sign in": "تسجيل الدخول",
    "Welcome back": "مرحباً بعودتك",
    "Sign in as the CDP Change Lead to manage nominations, assessments and approvals.": "سجّل الدخول بصفتك قائد التغيير لإدارة الترشيحات والتقييمات والاعتمادات.",
    "Password": "كلمة المرور",
    "That password is not correct.": "كلمة المرور غير صحيحة.",
    "Demo mode: no password has been set, so the password is <strong>demo</strong>. Set <code>CDP_LEAD_PASSWORD</code> before real use.":
        "وضع العرض التجريبي: لم تُضبط كلمة مرور، لذا كلمة المرور هي <strong>demo</strong>. اضبط <code>CDP_LEAD_PASSWORD</code> قبل الاستخدام الفعلي.",
    "Too many attempts. Please wait 15 minutes and try again.": "محاولات كثيرة جداً. يُرجى الانتظار 15 دقيقة ثم المحاولة مرة أخرى.",
    "This form has expired. Please reload the page and try again.": "انتهت صلاحية هذا النموذج. يُرجى إعادة تحميل الصفحة والمحاولة مرة أخرى.",
    # notices
    "Not available": "غير متاح",
    "Candidate not found.": "لم يُعثر على المرشح.",
    "Initiative not found.": "لم يُعثر على المبادرة.",
    "Unknown action": "إجراء غير معروف",
    "Document not available.": "المستند غير متاح.",
    "This assessment link has expired.": "انتهت صلاحية رابط التقييم هذا.",
    "This assessment link has been replaced or cancelled.": "تم استبدال رابط التقييم هذا أو إلغاؤه.",
    "This assessment link is not valid.": "رابط التقييم هذا غير صالح.",
    "Please contact the CDP Change Lead for a new link.": "يُرجى التواصل مع قائد التغيير للحصول على رابط جديد.",
    # audit
    "Imports, AI ratings, overrides, links, assessments, decisions and settings changes (latest 500).":
        "عمليات الاستيراد وتقييمات الذكاء الاصطناعي والتعديلات والروابط والتقييمات والقرارات وتغييرات الإعدادات (آخر 500).",
    "When": "الوقت", "Action": "الإجراء", "By": "بواسطة", "Nominee": "المرشح", "Detail": "التفاصيل",
    "lead": "قائد التغيير", "candidate": "المرشح", "system": "النظام", "unknown": "غير معروف",
    # dashboard
    "CDP Business User Champions": "أبطال مستخدمي الأعمال في المنصات الرقمية المشتركة",
    "Find the people who": "اعثر على الأشخاص الذين",
    "move colleagues forward": "يأخذون بأيدي زملائهم إلى الأمام",
    "Nominations, AI fit screening and LAUNCH WINDOW assessments across every initiative, in one place. Approve the champions who will help each entity adopt the Common Digital Platforms.":
        "الترشيحات، وفرز الملاءمة بالذكاء الاصطناعي، وتقييمات نافذة الإطلاق لكل المبادرات في مكان واحد. اعتمد الأبطال الذين سيساعدون كل جهة على تبنّي المنصات الرقمية المشتركة.",
    "Filters": "عوامل التصفية",
    "Initiative": "المبادرة", "All initiatives": "كل المبادرات", "All entities": "كل الجهات",
    "Fit category": "فئة الملاءمة", "All categories": "كل الفئات", "Apply": "تطبيق", "Clear": "مسح",
    "Champions nominated": "الأبطال المرشحون",
    "Approved champions": "الأبطال المعتمدون",
    "{n} nominee(s) not yet rated.": "عدد المرشحين الذين لم تُقيَّم ملاءمتهم بعد: {n}.",
    "By entity": "حسب الجهة",
    "Nominated": "المرشحون",
    "High": "عالية", "Moderate": "متوسطة", "Low": "منخفضة", "Doesn't fit": "غير ملائم",
    "Not rated": "غير مقيَّم",
    "No nominees match these filters.": "لا يوجد مرشحون مطابقون لعوامل التصفية هذه.",
    "Approved by category": "المعتمدون حسب الفئة",
    "Retry failed AI work and apply the retention policy": "إعادة محاولة مهام الذكاء الاصطناعي المتعثرة وتطبيق سياسة الاحتفاظ بالبيانات",
    "Run scheduled jobs now": "تشغيل المهام المجدولة الآن",
    "Initiatives": "المبادرات",
    "closed": "مغلقة",
    "{n} nominee(s)": "المرشحون: {n}",
    "Next: step {no}, {title}": "التالي: الخطوة {no}، {title}",
    "All steps complete": "اكتملت كل الخطوات",
    "{done} of {total} steps": "{done} من {total} خطوات",
    "No initiatives yet. Create the first one below.": "لا توجد مبادرات بعد. أنشئ أول مبادرة أدناه.",
    "Create an initiative": "إنشاء مبادرة",
    "Name *": "الاسم *", "Name": "الاسم",
    "e.g. ERP Release 3": "مثال: الإصدار 3 من نظام تخطيط الموارد",
    "Platform": "المنصة", "e.g. ERP": "مثال: نظام تخطيط الموارد",
    "Description": "الوصف",
    "Create initiative": "إنشاء المبادرة",
    "Nominees": "المرشحون", "(filtered)": "(بعد التصفية)",
    "CV fit": "ملاءمة السيرة الذاتية", "Outcome": "النتيجة",
    "No nominees yet.": "لا يوجد مرشحون بعد.",
    "Showing the first 200. Use the filters or the export to see the rest.": "تُعرض أول 200 فقط. استخدم عوامل التصفية أو التصدير لرؤية البقية.",
    # fit categories
    "High Fit": "ملاءمة عالية", "Moderate Fit": "ملاءمة متوسطة", "Low Fit": "ملاءمة منخفضة", "Doesn't Fit": "غير ملائم",
    "{f}: {n} of 4": "{f}: {n} من 4",
    "Not yet rated": "لم تُقيَّم بعد", "Not yet rated.": "لم تُقيَّم بعد.",
    "Specific, repeated CV evidence of using the nominated platform or workflow AND of supporting, training or guiding colleagues.":
        "أدلة محددة ومتكررة في السيرة الذاتية على استخدام المنصة أو إجراء العمل المرشَّح له، وعلى دعم الزملاء أو تدريبهم أو توجيههم.",
    "Relevant platform or workflow experience with some evidence of helping others, or strong peer support with limited platform evidence. Gaps to test in phase 2.":
        "خبرة ذات صلة بالمنصة أو بإجراء العمل مع بعض الأدلة على مساعدة الآخرين، أو دعم قوي للزملاء مع أدلة محدودة على استخدام المنصة. توجد فجوات تُختبر في المرحلة الثانية.",
    "Little relevant evidence: general administrative experience without platform use or peer support examples.":
        "أدلة قليلة ذات صلة: خبرة إدارية عامة دون أمثلة على استخدام المنصة أو دعم الزملاء.",
    "No relevant evidence for the champion role, or the CV is outside the role's scope.":
        "لا توجد أدلة ذات صلة بدور البطل، أو أن السيرة الذاتية خارج نطاق الدور.",
    # statuses
    "No Consent": "لا توجد موافقة", "Awaiting CV": "بانتظار السيرة الذاتية", "CV Unreadable": "تعذّرت قراءة السيرة الذاتية",
    "CV Uploaded": "تم تحميل السيرة الذاتية", "Shortlisted": "في القائمة المختصرة", "Not Shortlisted": "خارج القائمة المختصرة",
    "Invited": "تمت دعوته", "In Assessment": "قيد التقييم", "Assessing": "جارٍ التقييم الآلي",
    "Follow-up Requested": "طُلبت أسئلة متابعة", "Assessed": "تم التقييم", "Approved": "معتمد", "Not Approved": "غير معتمد",
    # outcomes and recommendations
    "Meets proposed assessment thresholds": "يستوفي حدود التقييم المقترحة",
    "Does not yet meet proposed assessment thresholds": "لا يستوفي حدود التقييم المقترحة بعد",
    "Additional evidence required": "مطلوب أدلة إضافية",
    "Remediation and reassessment required": "مطلوب معالجة وإعادة تقييم",
    "Incomplete—additional evidence required": "غير مكتمل: مطلوب أدلة إضافية",
    "Recommended for approval": "موصى بالاعتماد",
    "Not recommended at this stage": "غير موصى به في هذه المرحلة",
    "Not recommended until the safety concern is resolved": "غير موصى به حتى تُعالَج مسألة السلامة",
    "Evidence incomplete: decide with caution": "الأدلة غير مكتملة: اتخذ القرار بحذر",
    # steps
    "Collect nominations": "جمع الترشيحات", "Import survey results": "استيراد نتائج الاستبيان", "Upload CVs": "تحميل السير الذاتية",
    "AI fit rating": "تقييم الملاءمة بالذكاء الاصطناعي", "Review shortlist": "مراجعة القائمة المختصرة",
    "Send assessment links": "إرسال روابط التقييم", "Assessments completed": "اكتمال التقييمات",
    "Review reports": "مراجعة التقارير", "Approve champions": "اعتماد الأبطال",
    "Run the nomination survey in your survey tool (for example Microsoft Forms).": "أطلق استبيان الترشيح في أداة الاستبيانات لديك (مثل Microsoft Forms).",
    "Upload the survey export and check the matched columns.": "حمّل ملف تصدير الاستبيان وتحقق من الأعمدة المطابقة.",
    "Bulk upload the nominees' CVs (PDF or DOCX).": "حمّل السير الذاتية للمرشحين دفعة واحدة (PDF أو DOCX).",
    "Run the AI CV screening: High, Moderate, Low or Doesn't Fit.": "شغّل فرز السير الذاتية بالذكاء الاصطناعي: ملاءمة عالية أو متوسطة أو منخفضة أو غير ملائم.",
    "Check the shortlist and override any fit category with a reason.": "راجع القائمة المختصرة وعدّل أي فئة ملاءمة مع ذكر السبب.",
    "Copy each personal link or export the mail-merge list and send from your mailbox.": "انسخ كل رابط شخصي أو صدّر قائمة الدمج البريدي وأرسل الروابط من بريدك.",
    "Nominees complete the LAUNCH WINDOW assessment; the AI assesses their evidence.": "يُكمل المرشحون تقييم نافذة الإطلاق، ويقيّم الذكاء الاصطناعي أدلتهم.",
    "Read each candidate's assessment report.": "اقرأ تقرير التقييم لكل مرشح.",
    "Approve or decline each assessed candidate with a short rationale.": "اعتمد كل مرشح تم تقييمه أو اعتذر عنه مع مبرر موجز.",
    # initiative page
    "Champion journey: {done} of {total} steps": "رحلة الأبطال: {done} من {total} خطوات",
    "Step {no} completed {date}": "اكتملت الخطوة {no} بتاريخ {date}",
    "Reopen this step to make changes.": "أعد فتح هذه الخطوة لإجراء تغييرات.",
    "Reopen": "إعادة فتح", "Step tracker": "متتبع الخطوات", "Steps": "الخطوات", "next": "التالية",
    "Completed {date}": "اكتملت بتاريخ {date}",
    "Reopen step {no}": "إعادة فتح الخطوة {no}", "Mark step {no} complete": "تحديد الخطوة {no} كمكتملة", "Mark complete": "تحديد كمكتملة",
    "Step 2 · Import survey results": "الخطوة 2 · استيراد نتائج الاستبيان",
    "Upload the Excel or CSV export from your survey tool. You'll check the matched columns before anything is imported.":
        "حمّل ملف Excel أو CSV المصدَّر من أداة الاستبيانات. ستتحقق من الأعمدة المطابقة قبل استيراد أي بيانات.",
    "Survey export file": "ملف تصدير الاستبيان", "Upload survey file": "تحميل ملف الاستبيان",
    "Step 3 · Upload CVs": "الخطوة 3 · تحميل السير الذاتية",
    "Select many files at once. Files are matched to nominees by name in the file name (e.g. <code>Aisha_Rahman_CV.pdf</code>; two parts of the name are enough). On the next page, pick the nominee for any file that wasn't matched.":
        "اختر ملفات متعددة دفعة واحدة. تُطابَق الملفات مع المرشحين من خلال الاسم الوارد في اسم الملف (مثل <code>Aisha_Rahman_CV.pdf</code>، ويكفي جزءان من الاسم). في الصفحة التالية، اختر المرشح لأي ملف لم تتم مطابقته.",
    "CV files": "ملفات السير الذاتية",
    "Step 4 · AI fit rating": "الخطوة 4 · تقييم الملاءمة بالذكاء الاصطناعي",
    "{n} CV(s) ready to screen. Only nominees with recorded consent are screened. High and Moderate Fit are shortlisted automatically; you can change any category with a reason on the nominee's page.":
        "عدد السير الذاتية الجاهزة للفرز: {n}. لا يُفرز إلا المرشحون الذين سُجّلت موافقتهم. يُضاف أصحاب الملاءمة العالية والمتوسطة إلى القائمة المختصرة تلقائياً، ويمكنك تغيير أي فئة مع ذكر السبب في صفحة المرشح.",
    "Why nothing is ready:": "لماذا لا يوجد شيء جاهز:",
    "no nominees yet. Import the survey results first (step 2).": "لا يوجد مرشحون بعد. استورد نتائج الاستبيان أولاً (الخطوة 2).",
    "{n} nominee(s) have no consent recorded (status <em>No Consent</em>).": "عدد المرشحين دون موافقة مسجّلة: {n} (الحالة <em>لا توجد موافقة</em>).",
    "{n} nominee(s) have no CV yet (step 3).": "عدد المرشحين دون سيرة ذاتية بعد: {n} (الخطوة 3).",
    "{n} CV(s) could not be read; upload a text-based PDF or Word file on the nominee's page.": "عدد السير الذاتية التي تعذّرت قراءتها: {n}. حمّل ملف PDF نصياً أو ملف Word في صفحة المرشح.",
    "{n} nominee(s) are already rated.": "عدد المرشحين الذين قُيّمت ملاءمتهم مسبقاً: {n}.",
    "Record consent for all {n} nominee(s) without it": "تسجيل الموافقة لكل المرشحين الذين لا توجد لهم موافقة ({n})",
    "I confirm these nominees agreed to AI screening of their CV (for example by email or in a meeting).": "أؤكد أن هؤلاء المرشحين وافقوا على فرز سيرهم الذاتية بالذكاء الاصطناعي (مثلاً عبر البريد الإلكتروني أو في اجتماع).",
    "Record consent": "تسجيل الموافقة",
    "Run AI fit rating": "تشغيل تقييم الملاءمة بالذكاء الاصطناعي",
    "Step 6 · Send assessment links": "الخطوة 6 · إرسال روابط التقييم",
    "{n} shortlisted candidate(s). Download a mail-merge list (name, email, personal link) and send the links from your own mailbox. Creating links again replaces older ones.":
        "عدد المرشحين في القائمة المختصرة: {n}. نزّل قائمة الدمج البريدي (الاسم، البريد الإلكتروني، الرابط الشخصي) وأرسل الروابط من بريدك. إنشاء الروابط مجدداً يستبدل الروابط السابقة.",
    "Download links for candidates without one": "تنزيل الروابط للمرشحين الذين ليس لديهم رابط",
    "Recreate all links": "إعادة إنشاء كل الروابط",
    "Filter by status": "التصفية حسب الحالة", "All statuses": "كل الحالات", "Filter": "تصفية", "Export (CSV)": "تصدير (CSV)",
    "CV": "السيرة الذاتية", "(changed)": "(معدَّلة)",
    "No nominees yet. Import the survey results (step 2).": "لا يوجد مرشحون بعد. استورد نتائج الاستبيان (الخطوة 2).",
    "Edit or close this initiative": "تعديل هذه المبادرة أو إغلاقها",
    "Reopen initiative": "إعادة فتح المبادرة", "Close initiative": "إغلاق المبادرة",
    "Clear stored data for this initiative": "مسح البيانات المحفوظة لهذه المبادرة",
    "This permanently deletes every nominee record in <strong>{name}</strong>: survey rows, CV files, AI ratings, answers, game records, links, reports, decisions and their audit entries. It cannot be undone. Export the register first if you need a copy.":
        "يحذف هذا الإجراء نهائياً كل سجلات المرشحين في <strong>{name}</strong>: صفوف الاستبيان، وملفات السير الذاتية، وتقييمات الذكاء الاصطناعي، والإجابات، وسجلات اللعبة، والروابط، والتقارير، والقرارات، وقيودها في سجل التدقيق. لا يمكن التراجع عنه. صدّر السجل أولاً إن احتجت إلى نسخة.",
    "What to delete": "ما الذي سيُحذف",
    "Nominee data only (keep the initiative and reset its steps)": "بيانات المرشحين فقط (مع الإبقاء على المبادرة وإعادة ضبط خطواتها)",
    "Nominee data and the initiative itself": "بيانات المرشحين والمبادرة نفسها",
    "Type the initiative's name to confirm: <strong>{name}</strong>": "اكتب اسم المبادرة للتأكيد: <strong>{name}</strong>",
    "Delete permanently": "حذف نهائي",
    # import and CV results
    "Check the survey columns": "التحقق من أعمدة الاستبيان",
    "{n} row(s). Match each field to a column from your survey. The tool remembers these choices for next time.": "عدد الصفوف: {n}. طابِق كل حقل مع عمود من الاستبيان. تتذكر الأداة هذه الاختيارات للمرة القادمة.",
    "Field": "الحقل", "Survey column": "عمود الاستبيان", "Example value": "قيمة مثال",
    "— not in survey —": "— غير موجود في الاستبيان —",
    "Nominees without a \"yes\" in the consent column are imported as <strong>No Consent</strong> and won't be screened by AI until you record their consent.":
        "المرشحون الذين لا تحمل خانة الموافقة لديهم «نعم» يُستورَدون بحالة <strong>لا توجد موافقة</strong>، ولن يفرزهم الذكاء الاصطناعي حتى تسجّل موافقتهم.",
    "Import {n} row(s)": "استيراد الصفوف ({n})", "Cancel": "إلغاء",
    "First rows of the file": "الصفوف الأولى من الملف",
    "Nomination route (self / peer / manager)": "مسار الترشيح (ذاتي / زميل / مدير)",
    "Nominator name": "اسم المُرشِّح", "Nominator email": "البريد الإلكتروني للمُرشِّح",
    "Reason for nomination": "سبب الترشيح", "Line manager name": "اسم المدير المباشر", "Line manager email": "البريد الإلكتروني للمدير المباشر",
    "Nominee consent to AI screening": "موافقة المرشح على الفرز بالذكاء الاصطناعي",
    "CV upload results": "نتائج تحميل السير الذاتية",
    "Matched ({n})": "تمت المطابقة ({n})", "File": "الملف", "Result": "النتيجة", "None.": "لا يوجد.",
    "Choose the nominee for these files ({n})": "اختر المرشح لهذه الملفات ({n})",
    "This initiative has no nominees yet. Import the survey results (step 2) first, then upload the CVs again.": "لا يوجد مرشحون في هذه المبادرة بعد. استورد نتائج الاستبيان (الخطوة 2) أولاً، ثم حمّل السير الذاتية مرة أخرى.",
    "These files could not be matched with certainty. <strong>Pick the right nominee for each file</strong>, then click <em>Assign CVs</em>. Suggested matches are pre-selected; check them.":
        "تعذّرت مطابقة هذه الملفات بشكل مؤكد. <strong>اختر المرشح الصحيح لكل ملف</strong>، ثم انقر <em>إسناد السير الذاتية</em>. المطابقات المقترحة محددة مسبقاً؛ تحقق منها.",
    "Nominee for {file}": "المرشح للملف {file}", "— skip this file —": "— تخطَّ هذا الملف —", " (suggested)": " (مقترح)",
    "Assign CVs": "إسناد السير الذاتية", "Back to the initiative": "العودة إلى المبادرة",
    "text read": "تمت قراءة النص", "ok": "سليم", "unreadable": "تعذّرت القراءة", "unsupported": "غير مدعوم",
    # nominee page
    "Assessment": "التقييم", "Open assessment report": "فتح تقرير التقييم", "Nomination": "الترشيح",
    "Email": "البريد الإلكتروني", "Platform / workflow": "المنصة / إجراء العمل", "Route": "المسار",
    "self": "ترشيح ذاتي", "peer": "ترشيح من زميل", "manager": "ترشيح من المدير",
    "by {name}": "بواسطة {name}", "Line manager": "المدير المباشر", "Reason": "السبب",
    "Consent to AI screening": "الموافقة على الفرز بالذكاء الاصطناعي", "Recorded": "مسجّلة", "Not recorded": "غير مسجّلة",
    "Consent before assessment": "الموافقة قبل التقييم", "Not yet": "ليس بعد",
    "If the nominee has agreed outside the survey (for example by email), record it here.": "إذا وافق المرشح خارج الاستبيان (مثلاً عبر البريد الإلكتروني)، فسجّل موافقته هنا.",
    "Record consent to AI screening": "تسجيل الموافقة على الفرز بالذكاء الاصطناعي",
    "No CV uploaded.": "لم تُحمَّل سيرة ذاتية.", "CV file": "ملف السيرة الذاتية", "Replace CV": "استبدال السيرة الذاتية",
    "AI CV fit rating": "تقييم ملاءمة السيرة الذاتية بالذكاء الاصطناعي",
    "AI rating:": "تقييم الذكاء الاصطناعي:", "your rating:": "تقييمك:", "Reason:": "السبب:", "AI rating": "تقييم الذكاء الاصطناعي",
    "Evidence in the CV": "الأدلة في السيرة الذاتية", "None found.": "لم يُعثر على شيء.", "Gaps": "الفجوات", "None noted.": "لا توجد ملاحظات.",
    "What phase 2 should explore": "ما ينبغي أن تستكشفه المرحلة الثانية",
    "A CV shows experience, not behaviour. This rating is a screening step; the phase 2 assessment tests behaviour.": "تُظهر السيرة الذاتية الخبرة لا السلوك. هذا التقييم خطوة فرز، أما تقييم المرحلة الثانية فيختبر السلوك.",
    "Change the fit category": "تغيير فئة الملاءمة", "Reason *": "السبب *", "Save category": "حفظ الفئة",
    "Phase 2 assessment link": "رابط تقييم المرحلة الثانية",
    "<strong>New personal link</strong> (shown only now; copy it into your email):": "<strong>رابط شخصي جديد</strong> (يظهر الآن فقط؛ انسخه إلى رسالتك):",
    "Assessment link": "رابط التقييم", "Copied": "تم النسخ", "Copy": "نسخ",
    "Active link ending …{hint} · expires {date}": "رابط فعّال ينتهي بـ …{hint} · تنتهي صلاحيته في {date}",
    "last opened {date}": "آخر فتح في {date}", "Create a new link": "إنشاء رابط جديد", "Create link": "إنشاء رابط", "Cancel link": "إلغاء الرابط",
    "Extra time for the timed game (reasonable adjustment)": "وقت إضافي للعبة المحددة بوقت (ترتيب تيسيري)",
    "Links are available once the candidate is shortlisted.": "تتوفر الروابط بعد إضافة المرشح إلى القائمة المختصرة.",
    "Mode:": "النمط:", "Game:": "اللعبة:", "finished": "انتهت",
    "LAUNCH WINDOW game": "لعبة نافذة الإطلاق", "written version": "النسخة المكتوبة", "offline document": "مستند ورقي",
    "not chosen yet": "لم يُختر بعد", "not started": "لم تبدأ", "prologue": "التمهيد",
    "Act I · briefing": "الفصل الأول · الإحاطة", "Act II · crew rounds": "الفصل الثاني · جولات الطاقم",
    "Act III · anomaly": "الفصل الثالث · الخلل", "Act IV · final checks": "الفصل الرابع · الفحوص النهائية",
    "handover": "التسليم", "launch": "الإطلاق", "real-work questions": "أسئلة العمل الفعلي", "in progress": "قيد التقدم",
    "extra time {x}×": "وقت إضافي {x}×", "{n} moves recorded": "الخطوات المسجّلة: {n}", "ended by the clock": "انتهت بانتهاء الوقت",
    "Game outcome (not part of the score):": "نتيجة اللعبة (ليست جزءاً من الدرجة):",
    "rank {x}": "الرتبة {x}", "crew trust {x}": "ثقة الطاقم {x}", "launch readiness {x}": "جاهزية الإطلاق {x}",
    "crew built {x}": "أعضاء الطاقم المطوَّرون {x}", "safety lock {x}": "قفل الأمان: {x}",
    "overridden": "تم تجاوزه", "held": "بقي مُفعّلاً",
    "If the candidate had a technical problem, you can discard the unfinished game so they can restart or use the written version.": "إذا واجه المرشح مشكلة تقنية، يمكنك إلغاء اللعبة غير المكتملة ليبدأ من جديد أو يستخدم النسخة المكتوبة.",
    "Reset unfinished game": "إعادة ضبط اللعبة غير المكتملة",
    "AI assessment in progress.": "التقييم بالذكاء الاصطناعي جارٍ.", "Retry AI assessment": "إعادة محاولة التقييم بالذكاء الاصطناعي",
    "Follow-up questions ({n})": "أسئلة المتابعة ({n})", "Round {n}": "الجولة {n}", "Awaiting answer": "بانتظار الإجابة",
    "clarification": "استيضاح", "remediation": "معالجة",
    "Enter answers from the offline document": "إدخال الإجابات من المستند الورقي",
    "For candidates who could not use the link: paste their written answers to the LAUNCH WINDOW written scenarios. They are assessed the same way.": "للمرشحين الذين تعذّر عليهم استخدام الرابط: الصق إجاباتهم المكتوبة عن مواقف نافذة الإطلاق المكتوبة، وستُقيَّم بالطريقة نفسها.",
    "Save and assess": "حفظ وتقييم",
    "{decision} on {date}:": "{decision} بتاريخ {date}:", "Not approved": "غير معتمد",
    "Approve as champion": "اعتماده بطلاً", "Not approve": "عدم الاعتماد", "Rationale *": "المبررات *",
    "Update decision": "تحديث القرار", "Records and history": "السجلات والتاريخ",
    "Withdraw candidate": "سحب ترشيح المرشح", "Withdraw": "سحب",
    "Delete CV and stored evidence": "حذف السيرة الذاتية والأدلة المحفوظة", "Delete documents": "حذف المستندات",
    "Original survey row": "صف الاستبيان الأصلي",
    # assessment, score table
    "Evidence behind each rating (two independent AI assessments)": "الأدلة وراء كل درجة (تقييمان مستقلان بالذكاء الاصطناعي)",
    "Assessment A": "التقييم أ", "Assessment B": "التقييم ب",
    "Not yet assessed": "لم يُقيَّم بعد", "not yet assessed": "لم يُقيَّم بعد",
    "evidence {x}": "الأدلة: {x}", "strong": "قوية", "moderate": "متوسطة", "limited": "محدودة",
    "inadequate": "غير كافٍ", "unsafe": "غير آمن",
    "Missing:": "الناقص:", "Contradictions:": "التناقضات:", "possible safety concern": "مسألة سلامة محتملة", " (serious)": " (جسيمة)",
    "The last AI assessment attempt failed: {error}": "فشلت آخر محاولة للتقييم بالذكاء الاصطناعي: {error}",
    "No assessment yet.": "لا يوجد تقييم بعد.",
    "SIMULATED · demo assessor": "محاكاة · مقيّم تجريبي", "AI-generated · live": "مُنشأ بالذكاء الاصطناعي · فعلي",
    "Criterion": "المعيار", "Weight": "الوزن", "Rating": "الدرجة", "Points": "النقاط", "Minimum": "الحد الأدنى", "Moderation": "التحكيم",
    "below": "دون الحد", "met": "مستوفى",
    "agreed": "متفق عليه", "re-evaluated": "أُعيد تقييمه",
    "Score:": "الدرجة:", "Threshold:": "حد القبول:", "Evidence coverage:": "تغطية الأدلة:",
    # report
    "Report": "التقرير", "Assessment report: {name}": "تقرير التقييم: {name}",
    "This report is <strong>AI-generated and provisional</strong>": "هذا التقرير <strong>مُنشأ بالذكاء الاصطناعي ومبدئي</strong>",
    ", produced by the <strong>SIMULATED</strong> demo assessor, not live AI": "، أعدّه المقيّم التجريبي <strong>المحاكي</strong> لا الذكاء الاصطناعي الفعلي",
    ". Two independent AI assessments were compared by an AI moderator; agreement shows scoring consistency, not verification of CV claims. Weights and thresholds are proposed settings to calibrate in a pilot. The decision rests with the CDP Change Lead.":
        ". قارن محكِّم بالذكاء الاصطناعي بين تقييمين مستقلين؛ ويدل اتفاقهما على اتساق التقدير، لا على التحقق من صحة ما ورد في السيرة الذاتية. الأوزان وحدود القبول إعدادات مقترحة تُعايَر في مرحلة تجريبية. والقرار لقائد التغيير.",
    "Summary": "الملخص", "Recommendation": "التوصية", "Assessment score": "درجة التقييم",
    "Strengths shown": "نقاط القوة الظاهرة", "None rated 4 or above.": "لا توجد درجة 4 أو أعلى.",
    "Development areas": "مجالات التطوير", "None rated 2 or below.": "لا توجد درجة 2 أو أقل.",
    "A possible safety concern was identified in: {areas}.": "رُصدت مسألة سلامة محتملة في: {areas}.", ", ": "، ",
    "Phase 1: CV fit": "المرحلة الأولى: ملاءمة السيرة الذاتية",
    ", changed by the Change Lead to": "، وعدّلها قائد التغيير إلى", "Gaps:": "الفجوات:", "Not rated.": "لم تُقيَّم.",
    "Phase 2: game outcome": "المرحلة الثانية: نتيجة اللعبة",
    "LAUNCH WINDOW rank: {x}": "رتبة نافذة الإطلاق: {x}", "Crew trust: {x}": "ثقة الطاقم: {x}", "Launch readiness: {x}": "جاهزية الإطلاق: {x}",
    "Crew members built up: {x}": "أعضاء الطاقم الذين طوّرهم: {x}", "Safety lock: {x}": "قفل الأمان: {x}",
    "Completed through the written scenarios (no game outcome).": "أُكمل من خلال المواقف المكتوبة (لا توجد نتيجة لعبة).", "Not played.": "لم يلعب.",
    "The game outcome is shown for context only. It is not part of the assessment score.": "تُعرض نتيجة اللعبة للاستئناس فقط، وليست جزءاً من درجة التقييم.",
    "Phase 2: behavioural assessment": "المرحلة الثانية: التقييم السلوكي",
    "Assessment mode:": "نمط التقييم:", "written scenarios": "المواقف المكتوبة", "offline document entered by the Change Lead": "مستند ورقي أدخله قائد التغيير",
    "evidence version {v}": "إصدار الأدلة {v}", "settings version {v}": "إصدار الإعدادات {v}",
    "<strong>{decision}</strong> by the CDP Change Lead on {date}.": "<strong>{decision}</strong> بقرار من قائد التغيير بتاريخ {date}.",
    "Rationale:": "المبررات:", "No decision recorded yet.": "لم يُسجَّل قرار بعد.", "Print or save as PDF": "طباعة أو حفظ بصيغة PDF",
    # settings
    "Service": "الخدمة", "AI:": "الذكاء الاصطناعي:", "demo": "تجريبي", "live": "فعلي",
    "Live AI assessment enabled.": "التقييم الفعلي بالذكاء الاصطناعي مفعّل.",
    "CDP_AI_MODE=live was requested but ANTHROPIC_API_KEY is missing.": "طُلب الإعداد CDP_AI_MODE=live لكن المفتاح ANTHROPIC_API_KEY غير موجود.",
    "CDP_AI_MODE is not set to 'live'.": "الإعداد CDP_AI_MODE غير مضبوط على 'live'.",
    "Live AI needs <code>ANTHROPIC_API_KEY</code> and <code>CDP_AI_MODE=live</code> in the hosting settings. The Change Lead password is <code>CDP_LEAD_PASSWORD</code>.":
        "يحتاج الذكاء الاصطناعي الفعلي إلى <code>ANTHROPIC_API_KEY</code> و<code>CDP_AI_MODE=live</code> في إعدادات الاستضافة. كلمة مرور قائد التغيير هي <code>CDP_LEAD_PASSWORD</code>.",
    "Assessment scorecard": "بطاقة التقييم", "Proposed settings — require pilot validation": "إعدادات مقترحة تتطلب التحقق في مرحلة تجريبية",
    "Current version: v{v}. Each assessment records the version it used. Weights must total 100.": "الإصدار الحالي: v{v}. يسجّل كل تقييم الإصدار الذي استخدمه. يجب أن يكون مجموع الأوزان 100.",
    "Weight (%)": "الوزن (%)", "Minimum rating": "الحد الأدنى للدرجة", "Weight for {name}": "الوزن لمعيار {name}", "Minimum for {name}": "الحد الأدنى لمعيار {name}",
    "none": "لا يوجد", "Overall threshold (/100)": "حد القبول العام (من 100)", "Follow-up rounds allowed": "عدد جولات المتابعة المسموح بها",
    "Game time limit (minutes)": "مدة اللعبة (بالدقائق)", "Assessment link valid for (days)": "مدة صلاحية رابط التقييم (بالأيام)",
    "Keep CVs of closed records for (days)": "مدة الاحتفاظ بالسير الذاتية للسجلات المغلقة (بالأيام)",
    "Change note *": "ملاحظة التغيير *", "Why is this changing?": "لماذا يتم هذا التغيير؟", "Save as a new version": "الحفظ كإصدار جديد",
    "Fit categories (CV screening)": "فئات الملاءمة (فرز السير الذاتية)", "High and Moderate Fit are shortlisted for phase 2.": "يُضاف أصحاب الملاءمة العالية والمتوسطة إلى القائمة المختصرة للمرحلة الثانية.",
    "Settings history": "سجل الإعدادات", "Initial proposed settings": "الإعدادات المقترحة الأولية",
    # written scenarios (same wording as the game's Arabic script)
    "LAUNCH WINDOW scenario: Ali, a technician at the launch base, keeps asking you to do his valve checks for him. Other new crew members are watching what you do. How would you help Ali so he can do the checks himself, and how would you know others were starting to copy the approach?":
        "موقف من نافذة الإطلاق: علي، فني في قاعدة الإطلاق، يطلب منك باستمرار أن تُجري عنه فحوص الصمامات. وأعضاء الطاقم الجدد الآخرون يراقبون ما تفعله. كيف تساعد علياً ليُجري الفحوص بنفسه، وكيف ستعرف أن الآخرين بدؤوا يتبعون الأسلوب نفسه؟",
    "LAUNCH WINDOW scenario: coach Noor, a nervous rookie technician doing her first fuel-system check, who is anxious about getting it wrong. Reply to each of Noor's messages.":
        "موقف من نافذة الإطلاق: درّب نور، الفنية المبتدئة المتوترة التي تُجري أول فحص لنظام الوقود وتخشى أن تخطئ. ردّ على كل رسالة من رسائل نور.",
    "LAUNCH WINDOW scenario: early in the shift you promised Rashid you would return his pre-flight checklist before T−5. Then an anomaly puts the count on hold and your time is cut. What do you do about your promise, who do you tell, and how do you track it through to closure or hand-over?":
        "موقف من نافذة الإطلاق: في بداية المناوبة وعدت راشد بأن تعيد إليه قائمة فحص ما قبل الإطلاق قبل T−5. ثم أوقف خلل ما العدّ التنازلي وتقلّص وقتك. ماذا تفعل بشأن وعدك، ومن تُبلغ، وكيف تتابعه حتى يُغلق أو يُسلَّم لغيرك؟",
    "LAUNCH WINDOW scenario: halfway through the countdown, Range Safety changes the launch rules and your current plan no longer works. How do you find out what changed, what questions do you ask, and how do you check your new plan is right before using it?":
        "موقف من نافذة الإطلاق: في منتصف العدّ التنازلي، غيّرت سلامة المدى قواعد الإطلاق ولم تعد خطتك الحالية صالحة. كيف تعرف ما الذي تغيّر، وما الأسئلة التي تطرحها، وكيف تتحقق من صحة خطتك الجديدة قبل تطبيقها؟",
    "LAUNCH WINDOW scenario: walk through the fuel-system check before launch. Explain its purpose, the main steps, the exceptions you expect, and when you would stop and refer the problem to someone else.":
        "موقف من نافذة الإطلاق: اشرح فحص نظام الوقود قبل الإطلاق خطوة بخطوة: الغرض منه، وخطواته الرئيسية، والاستثناءات التي تتوقعها، ومتى تتوقف وتحيل المشكلة إلى شخص آخر.",
    "LAUNCH WINDOW stress moment: the Flight Director orders you to override the pad safety lock so the launch window isn't lost, and says he will take responsibility. You have 90 seconds. What do you do and say?":
        "لحظة ضغط في نافذة الإطلاق: يأمرك مدير الرحلة بتجاوز قفل الأمان في منصة الإطلاق حتى لا تضيع نافذة الإطلاق، ويقول إنه سيتحمل المسؤولية. أمامك 90 ثانية. ماذا تفعل وماذا تقول؟",
    "Noor: I'm going to get this wrong. It's my first fuel-system check, and everyone's watching.": "نور: سأخطئ في هذا حتماً. إنه أول فحص لي لنظام الوقود، والجميع يراقبني.",
    "Noor: I did what you said and the pressure light just went amber. Did I break it?": "نور: فعلت ما قلته لي، والآن صار مؤشر الضغط كهرمانياً. هل أفسدت شيئاً؟",
    "Noor: Can you just do it yourself? I'll never remember these steps for next time.": "نور: هل يمكنك أن تقوم بها بنفسك فقط؟ لن أتذكر هذه الخطوات في المرة القادمة أبداً.",
    "What is the fuel-system check for, and who depends on it?": "ما الغرض من فحص نظام الوقود، ومن يعتمد عليه؟",
    "What are the main steps?": "ما الخطوات الرئيسية؟",
    "What exceptions or problems do you expect along the way?": "ما الاستثناءات أو المشكلات التي تتوقعها في أثناء ذلك؟",
    "When would you stop and refer the problem, and to whom (for example the fuel bay, the access desk, or Range Safety)?": "متى تتوقف وتحيل المشكلة، وإلى من (مثل حجرة الوقود، أو مكتب الصلاحيات، أو سلامة المدى)؟",
    # candidate assessment page (game choice)
    "Your game is saved": "لعبتك محفوظة",
    "Continue where you left off. The clock keeps running while you are away.": "تابع من حيث توقفت. يستمر الوقت في العدّ أثناء غيابك.",
    "Continue the game": "متابعة اللعبة",
    "Choose how to take the assessment": "اختر طريقة أداء التقييم",
    "Extra time has been added for you:": "أُضيف لك وقت إضافي:",
    "Written version": "النسخة المكتوبة",
    "Untimed, and works well with screen readers and on phones.": "دون وقت محدد، وتعمل جيداً مع قارئات الشاشة وعلى الهواتف.",
    "Use the written version": "استخدام النسخة المكتوبة",
    "Both versions are assessed against the same scorecard. Once you start one, you cannot switch.": "تُقيَّم النسختان وفق بطاقة التقييم نفسها. وبعد أن تبدأ إحداهما لا يمكنك التبديل.",
    "Choose file": "اختر ملفاً", "Choose files": "اختر الملفات", "No file chosen": "لم يُختر ملف", "{n} files chosen": "الملفات المختارة: {n}",
    # server messages (exact)
    "Initiative created. Start with step 1.": "تم إنشاء المبادرة. ابدأ بالخطوة 1.",
    "Initiative updated.": "تم تحديث المبادرة.",
    "Nothing was deleted. Type the initiative's name exactly to confirm.": "لم يُحذف شيء. اكتب اسم المبادرة كما هو تماماً للتأكيد.",
    "The initiative was removed.": "تمت إزالة المبادرة.", "Steps were reset.": "أُعيد ضبط الخطوات.",
    "Reopen it to make changes.": "أعد فتحها لإجراء تغييرات.",
    "Choose the survey export file (Excel or CSV).": "اختر ملف تصدير الاستبيان (Excel أو CSV).",
    "The uploaded file has expired. Please upload it again.": "انتهت صلاحية الملف المحمَّل. يُرجى تحميله مرة أخرى.",
    "Choose one or more CV files (PDF or DOCX).": "اختر ملف سيرة ذاتية واحداً أو أكثر (PDF أو DOCX).",
    "No CVs were assigned: no nominee was chosen for the files. Upload them again and pick the nominee for each file on the next page.":
        "لم تُسنَد أي سيرة ذاتية: لم يُختر مرشح للملفات. حمّلها مرة أخرى واختر المرشح لكل ملف في الصفحة التالية.",
    "Tick the box to confirm these nominees agreed to AI screening.": "ضع علامة في المربع لتأكيد موافقة هؤلاء المرشحين على الفرز بالذكاء الاصطناعي.",
    "No CVs are waiting for screening.": "لا توجد سير ذاتية بانتظار الفرز.",
    "Refresh the page in a moment to see the results.": "حدّث الصفحة بعد لحظات لرؤية النتائج.",
    "Choose a CV file.": "اختر ملف سيرة ذاتية.", "CV uploaded.": "تم تحميل السيرة الذاتية.",
    "Offline answers saved. AI assessment started.": "تم حفظ الإجابات الورقية. بدأ التقييم بالذكاء الاصطناعي.",
    "Saved.": "تم الحفظ.",
    "Please tick the consent box to continue, or contact the CDP Change Lead if you do not wish to take part.": "يُرجى وضع علامة في مربع الموافقة للمتابعة، أو التواصل مع قائد التغيير إن كنت لا ترغب في المشاركة.",
    "Thank you. Your answers have been submitted.": "شكراً لك. تم إرسال إجاباتك.",
    "Saved. You can come back to this link at any time.": "تم الحفظ. يمكنك العودة إلى هذا الرابط في أي وقت.",
    "You have already started the game. Contact the CDP Change Lead if you need the written version.": "لقد بدأت اللعبة بالفعل. تواصل مع قائد التغيير إن احتجت إلى النسخة المكتوبة.",
    # business-rule errors
    "This candidate has been withdrawn.": "تم سحب ترشيح هذا المرشح.",
    "Give the initiative a name, for example 'ERP Release 3'.": "أعطِ المبادرة اسماً، مثل «الإصدار 3 من نظام تخطيط الموارد».",
    "Unknown step.": "خطوة غير معروفة.", "Choose a fit category.": "اختر فئة الملاءمة.",
    "Record a reason for changing the AI's fit category.": "سجّل سبب تغيير فئة الملاءمة التي حددها الذكاء الاصطناعي.",
    "Run the AI fit rating first.": "شغّل تقييم الملاءمة بالذكاء الاصطناعي أولاً.",
    "The fit category can only be changed before an assessment link is sent.": "لا يمكن تغيير فئة الملاءمة إلا قبل إرسال رابط التقييم.",
    "Only shortlisted candidates can be sent an assessment link.": "لا يُرسل رابط التقييم إلا للمرشحين في القائمة المختصرة.",
    "Your answers can no longer be changed.": "لم يعد بالإمكان تغيير إجاباتك.",
    "Offline answers can only be added for shortlisted candidates who have not finished.": "لا يمكن إضافة الإجابات الورقية إلا للمرشحين في القائمة المختصرة الذين لم ينتهوا بعد.",
    "Please confirm your consent first.": "يُرجى تأكيد موافقتك أولاً.",
    "These answers have already been submitted.": "سبق إرسال هذه الإجابات.",
    "There are no follow-up questions to answer.": "لا توجد أسئلة متابعة للإجابة عنها.",
    "Please answer every follow-up question.": "يُرجى الإجابة عن كل أسئلة المتابعة.",
    "A candidate can be approved only after their assessment is complete.": "لا يمكن اعتماد المرشح إلا بعد اكتمال تقييمه.",
    "Choose Approve or Not approve.": "اختر الاعتماد أو عدم الاعتماد.",
    "Record a short rationale for the decision.": "سجّل مبرراً موجزاً للقرار.",
    "Extra time must be between 1x and 3x.": "يجب أن يكون الوقت الإضافي بين 1× و3×.",
    "You have already started the written version.": "لقد بدأت النسخة المكتوبة بالفعل.",
    "The game has not been started.": "لم تبدأ اللعبة بعد.", "Only an unfinished game can be reset.": "لا يمكن إعادة ضبط إلا لعبة غير مكتملة.",
    # import and file errors
    "Save it again as .xlsx or .csv.": "احفظه مرة أخرى بصيغة \u200e.xlsx أو \u200e.csv.",
    "The CSV file's text encoding could not be read. Save it as 'CSV UTF-8'.": "تعذّرت قراءة ترميز نص ملف CSV. احفظه بصيغة 'CSV UTF-8'.",
    "Please upload the survey results as an Excel (.xlsx) or CSV file.": "يُرجى تحميل نتائج الاستبيان كملف Excel \u200f(\u200e.xlsx) أو CSV.",
    "The file has no data rows under the header row.": "لا يحتوي الملف على صفوف بيانات تحت صف العناوين.",
    "The file is empty.": "الملف فارغ.", "The file is larger than 8 MB.": "حجم الملف أكبر من 8 ميغابايت.",
    "Please upload a PDF or DOCX file.": "يُرجى تحميل ملف PDF أو DOCX.", "The PDF is password-protected.": "ملف PDF محمي بكلمة مرور.",
    "Little or no text could be read (it may be a scanned image).": "تعذّرت قراءة نص يُذكر (قد يكون الملف صورة ممسوحة ضوئياً).",
    "Please upload a text-based PDF or DOCX, or enter details manually.": "يُرجى تحميل ملف PDF نصي أو DOCX، أو إدخال التفاصيل يدوياً.",
})

AR_PATTERNS: dict[str, str] = {
    # step tracker progress
    r"(\d+) nominations imported": "الترشيحات المستوردة: {0}",
    r"(\d+) nominees": "المرشحون: {0}",
    r"(\d+) of (\d+) CVs uploaded": "السير الذاتية المحمّلة: {0} من {1}",
    r"(\d+) of (\d+) screened": "تم فرز {0} من {1}",
    r"(\d+) shortlisted": "في القائمة المختصرة: {0}",
    r"(\d+) of (\d+) invited": "تمت دعوة {0} من {1}",
    r"(\d+) of (\d+) assessed": "تم تقييم {0} من {1}",
    r"(\d+) reports ready": "التقارير الجاهزة: {0}",
    r"(\d+) of (\d+) decided": "صدر القرار في {0} من {1}",
    # scores
    r"([\d.]+) points from ([\d.]+) assessed points; ([\d.]+) points remain unassessed\.": "{0} نقطة من {1} نقطة مقيَّمة؛ وتبقى {2} نقطة دون تقييم.",
    r"(\d+) of (\d+) criteria assessed": "تم تقييم {0} من {1} معايير",
    # flash messages
    r"Deleted (\d+) nominee record\(s\) and (\d+) CV file\(s\)\.": "تم حذف سجلات المرشحين ({0}) وملفات السير الذاتية ({1}).",
    r"Step (\d+) is marked complete\.": "الخطوة {0} محددة كمكتملة.",
    r"Imported (\d+) nominee\(s\); (\d+) duplicate\(s\) skipped\.": "تم استيراد {0} من المرشحين، وتخطي {1} من الترشيحات المكررة.",
    r"Notes: (.+)": "ملاحظات: {0}",
    r"Row (\d+): (.+) is already in this initiative \(duplicate nomination recorded\)\.": "الصف {0}: {1} موجود بالفعل في هذه المبادرة (سُجّل ترشيح مكرر).",
    r"Row (\d+): no nominee name, skipped\.": "الصف {0}: لا يوجد اسم للمرشح، تم تخطيه.",
    r"Row (\d+): no entity for (.+), skipped\.": "الصف {0}: لا توجد جهة لـ {1}، تم تخطيه.",
    r"Row (\d+): '(.+)' is not an email address; imported without email\.": "الصف {0}: '{1}' ليس عنوان بريد إلكتروني؛ تم الاستيراد دون بريد.",
    r"(\d+) CV\(s\) assigned\.": "تم إسناد السير الذاتية: {0}.",
    r"(\d+) file\(s\) were skipped; upload them again to assign them\.": "تم تخطي الملفات: {0}. حمّلها مرة أخرى لإسنادها.",
    r"Consent recorded for (\d+) nominee\(s\)\.": "سُجّلت الموافقة لعدد {0} من المرشحين.",
    r"AI fit rating started for (\d+) CV\(s\)\.": "بدأ تقييم الملاءمة بالذكاء الاصطناعي لعدد {0} من السير الذاتية.",
    r"Settings not saved: (.+)": "لم تُحفظ الإعدادات: {0}",
    r"Saved as configuration version (\d+)\.": "تم الحفظ كإصدار الإعدادات {0}.",
    r"Jobs complete: (\d+) assessment\(s\) completed, (\d+) CV screening\(s\) retried, (\d+) closed record\(s\) past retention cleared\.":
        "اكتملت المهام: تقييمات مكتملة {0}، ومحاولات فرز سير ذاتية مُعادة {1}، وسجلات مغلقة تجاوزت مدة الاحتفاظ ومُسحت {2}.",
    r"Match a column for: (.+)\.": "طابِق عموداً لكل من: {0}.",
    r"The Excel file could not be read \((\w+)\)\.": "تعذّرت قراءة ملف Excel \u200f({0}).",
    r"The file could not be read \((\w+)\)\.": "تعذّرت قراءة الملف ({0}).",
    r"AI screening could not run \((.+)\)\. The CV is saved; try again\.": "تعذّر تشغيل الفرز بالذكاء الاصطناعي ({0}). السيرة الذاتية محفوظة؛ حاول مرة أخرى.",
    r"AI assessment could not run \((.+)\)\. Answers are saved and will be retried\.": "تعذّر تشغيل التقييم بالذكاء الاصطناعي ({0}). الإجابات محفوظة وستُعاد المحاولة.",
}

# Game ranks come from the bilingual game script.
try:
    from app.launch_content import RANKS as _RANKS
    AR.update({r["en"]: r["ar"] for _f, r in _RANKS})
except Exception:  # pragma: no cover
    pass



# Messages built at run time (counts, row numbers, names). Each English pattern maps to an Arabic
# template that reuses the captured groups. Checked only when there is no exact match.
_PATTERNS: list[tuple[re.Pattern, str]] = [(re.compile(f"^{k}$"), v) for k, v in AR_PATTERNS.items()]
_SENTENCE = re.compile(r"(?<=[.!?…])\s+(?=[A-Z\"'(])")


_NEEDS_ISOLATE = re.compile(r"[A-Za-z\-/:.@_]")


def _iso(v):
    """Wrap a value placed inside Arabic text in Unicode first-strong isolates (the plain-text <bdi>)."""
    return f"\u2068{v}\u2069" if isinstance(v, str) and _NEEDS_ISOLATE.search(v) else v


def _group(g: str | None) -> str:
    """A captured piece of a message: translate it, or each item of a comma list."""
    if not g:
        return ""
    out = tr(g)
    if out == g and ", " in g:
        out = AR[", "].join(tr(x) for x in g.split(", "))
    return _iso(out) if out == g else out


def tr(text, lang: str = "ar") -> str:
    """Translate one string. Exact match first, then run-time patterns, then sentence by sentence."""
    if lang != "ar" or not text or not isinstance(text, str):
        return text
    hit = AR.get(text)
    if hit is not None:
        return hit
    for rx, tpl in _PATTERNS:
        m = rx.match(text)
        if m:
            return tpl.format(*[_group(g) for g in m.groups()])
    parts = _SENTENCE.split(text)
    if len(parts) > 1:
        return " ".join(tr(p) for p in parts)
    return text


def translator(lang: str):
    """`_` for templates: `_("Hello {name}", name=x)` translates, then fills placeholders.
    Plain strings are escaped by Jinja as usual."""
    def _(text, **kw):
        out = tr(text, lang)
        if kw and isinstance(out, str):
            return out.format(**({k: _iso(v) for k, v in kw.items()} if lang == "ar" else kw))
        return out
    return _


def html_translator(lang: str):
    """`_h` for template literals that contain markup. Only static, trusted keys may be passed;
    placeholder values are escaped."""
    def _h(text: str, **kw) -> Markup:
        out = Markup(tr(text, lang))
        if kw and lang == "ar":
            kw = {k: _iso(v) for k, v in kw.items()}
        return out.format(**kw) if kw else out
    return _h
