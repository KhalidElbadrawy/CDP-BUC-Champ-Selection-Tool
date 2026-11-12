"""The invitation email sent when the Change Lead presses Invite. Bilingual: English and Arabic,
in the order of the language the Change Lead is using."""
from __future__ import annotations

from datetime import date
from html import escape

SUBJECT = {
    "en": "Your invitation: CDP Business User Champion assessment",
    "ar": "دعوتك لتقييم أبطال مستخدمي الأعمال في المنصات الرقمية المشتركة",
}

AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]


def _date(iso: str, lang: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {AR_MONTHS[d.month - 1]} {d.year}" if lang == "ar" else f"{d.day} {d.strftime('%B')} {d.year}"


def _paragraphs(lang: str, name: str, initiative: str, expires: str) -> tuple[str, list[str], str, list[str]]:
    """greeting, paragraphs before the link, link label, paragraphs after the link."""
    if lang == "ar":
        return (
            f"عزيزي/عزيزتي {name}،",
            [f"يسعدنا إبلاغك بأنه تم ترشيحك ضمن القائمة المختصرة لتكون بطلاً لمستخدمي الأعمال في المنصات الرقمية المشتركة ({initiative}).",
             "الخطوة التالية تقييم قصير عبر الإنترنت بعنوان «نافذة الإطلاق»: لعبة قصصية تدور في الساعة الأخيرة قبل إطلاق صاروخ، "
             "يليها سؤالان قصيران عن عملك الفعلي. يستغرق نحو 35 دقيقة، ولا توجد أسئلة خادعة؛ تصرّف كما تتصرف فعلاً. "
             "يمكنك اختيار العربية أو الإنجليزية، وتتوفر نسخة مكتوبة إن كنت تفضّلها."],
            "رابطك الشخصي:",
            [f"هذا الرابط خاص بك، فيُرجى عدم مشاركته. تنتهي صلاحيته في {expires}. يُحفظ تقدّمك، لذا يمكنك التوقف والعودة لاحقاً.",
             "الأفضل استخدام حاسوب محمول أو جهاز لوحي مع تشغيل الصوت.",
             "إن كانت لديك أسئلة، أو احتجت إلى وقت إضافي أو أي ترتيب تيسيري آخر، فيُرجى الرد على هذه الرسالة.",
             "مع التحية،\nقائد التغيير\nالمنصات الرقمية المشتركة"],
        )
    return (
        f"Dear {name},",
        [f"We're pleased to let you know that you have been shortlisted as a possible CDP Business User Champion for {initiative}.",
         "The next step is a short online assessment called LAUNCH WINDOW: a story game set in the last hour before a rocket launch, "
         "followed by two short questions about your real work. It takes about 35 minutes. There are no trick questions; act as you "
         "really would. You can choose English or Arabic, and a written version is available if you prefer."],
        "Your personal link:",
        [f"This link is for you only, so please don't forward it. It expires on {expires}. Your progress is saved, so you can stop and come back.",
         "It works best on a laptop or tablet with the sound on.",
         "If you have questions, or need extra time or another adjustment, just reply to this email.",
         "Kind regards,\nCDP Change Lead\nCommon Digital Platforms"],
    )


def build(name: str, initiative: str, link: str, expires_iso: str, first: str = "en") -> tuple[str, str, str]:
    """Returns (subject, plain text, html)."""
    order = ["ar", "en"] if first == "ar" else ["en", "ar"]
    subject = f"{SUBJECT[order[0]]} | {SUBJECT[order[1]]}"

    text_parts, html_parts = [], []
    for lang in order:
        greet, before, label, after = _paragraphs(lang, name, initiative, _date(expires_iso, lang))
        text_parts.append("\n\n".join([greet, *before, f"{label}\n{link}", *after]))
        rtl = lang == "ar"
        p = ''.join(f'<p style="margin:0 0 14px">{escape(x).replace(chr(10), "<br>")}</p>' for x in before)
        q = ''.join(f'<p style="margin:0 0 14px">{escape(x).replace(chr(10), "<br>")}</p>' for x in after)
        html_parts.append(
            f'<div dir="{"rtl" if rtl else "ltr"}" lang="{lang}" style="text-align:{"right" if rtl else "left"};'
            f'font:15px/1.6 {"Tahoma," if rtl else ""}Segoe UI,Arial,sans-serif;color:#1b2333">'
            f'<p style="margin:0 0 14px">{escape(greet)}</p>{p}'
            f'<p style="margin:0 0 6px"><strong>{escape(label)}</strong></p>'
            f'<p style="margin:0 0 18px"><a href="{escape(link)}" dir="ltr" style="display:inline-block;padding:11px 20px;'
            f'background:#0b6fd6;color:#ffffff;border-radius:999px;text-decoration:none;font-weight:bold">'
            f'{"افتح التقييم" if rtl else "Open the assessment"}</a></p>'
            f'<p style="margin:0 0 18px;font-size:12px;color:#5a6478;word-break:break-all" dir="ltr">{escape(link)}</p>'
            f'{q}</div>')
    sep = "\n\n" + "-" * 40 + "\n\n"
    text = sep.join(text_parts)
    html = ('<!doctype html><html><body style="margin:0;padding:24px;background:#f3f5f9">'
            '<div style="max-width:620px;margin:0 auto;background:#ffffff;border-radius:16px;padding:28px">'
            + '<hr style="border:0;border-top:1px solid #e3e7ef;margin:24px 0">'.join(html_parts)
            + '</div></body></html>')
    return subject, text, html
