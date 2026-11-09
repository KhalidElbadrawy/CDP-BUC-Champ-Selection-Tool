"""LAUNCH WINDOW: every word the player reads or hears, in English and Arabic.

Voice lines are recorded files at /static/launch/vo/{lang}/{id}.mp3; the text here is their caption.
Nothing in the game mentions champions or the candidate's job; each scene is built so the six
assessed behaviours show up naturally (see app/game.py for the evidence mapping)."""
from __future__ import annotations


def L(en: str, ar: str) -> dict:
    return {"en": en, "ar": ar}


SPEAKERS = {
    "narrator": L("Narrator", "الراوي"),
    "maryam": L("Commander Maryam", "القائدة مريم"),
    "noor": L("Noor · fuel technician", "نور · فنية الوقود"),
    "saeed": L("Flight Director Saeed", "مدير الرحلة سعيد"),
    "hamad": L("Hamad · pad engineer (radio)", "حمد · مهندس المنصة (لاسلكي)"),
    "yousef": L("Yousef · mission control", "يوسف · غرفة التحكم"),
}

# Voice line id -> (speaker, caption)
LINES = {
    "N01": ("narrator", L("Sixty minutes to launch. When the window closes, there's no second chance. Everyone on this base is counting on everyone else. Your first stop is the briefing hall. It's glowing on your map.",
                          "ستون دقيقة على الإطلاق. عندما تُغلق النافذة، لا توجد فرصة ثانية. كل من في هذه القاعدة يعتمد على الآخرين. محطتك الأولى قاعة الإحاطة، وهي تتوهج على خريطتك.")),
    "N02": ("narrator", L("You have three minutes. Open up to four mission files, then answer three readiness checks.",
                          "لديك ثلاث دقائق. افتح ما يصل إلى أربعة ملفات مهمة، ثم أجب عن ثلاثة أسئلة جاهزية.")),
    "N03": ("narrator", L("The countdown is running. Your crew is calling for you. Start with Noor at the fuel bay. Her marker is pulsing on the map.",
                          "العد التنازلي جارٍ. طاقمك ينادي عليك. ابدأ بنور في محطة الوقود، علامتها تنبض على الخريطة.")),
    "N04": ("narrator", L("Other crew members need you too. Answer their calls, then head to mission control.",
                          "أفراد آخرون من الطاقم يحتاجونك أيضاً. أجب عن نداءاتهم، ثم توجّه إلى غرفة التحكم.")),
    "N05": ("narrator", L("Anomaly. The count is on hold. Get to mission control, now.",
                          "خلل طارئ. العد متوقف. توجّه إلى غرفة التحكم، الآن.")),
    "N06": ("narrator", L("Alerts are coming in. For each one: handle it yourself, send a crew member, or route it to the right station. Watch the clock.",
                          "التنبيهات تتوالى. لكل تنبيه: تعامل معه بنفسك، أو أرسل أحد أفراد طاقمك، أو أحِله إلى المحطة المسؤولة. راقب الوقت.")),
    "N07": ("narrator", L("Last wave. Two alerts, time for one. Choose.", "الموجة الأخيرة. تنبيهان، والوقت يكفي لواحد فقط. اختر.")),
    "N08": ("narrator", L("The count resumes at T-minus ten. Hamad is alone on the launch pad, and he needs you on the radio.",
                          "يُستأنف العد عند عشر دقائق قبل الإطلاق. حمد وحده على منصة الإطلاق، ويحتاجك على اللاسلكي.")),
    "N09": ("narrator", L("Your checklist is flashing. Promises are coming due. You can't do everything. Deliver, warn people early, or let one slip.",
                          "قائمة مهامك تومض. حان موعد الوفاء بالوعود. لا يمكنك إنجاز كل شيء. أنجز، أو نبّه الآخرين مبكراً، أو اترك أحدها يفوت.")),
    "N10": ("narrator", L("Five minutes to launch. Commander Maryam wants your handover.", "خمس دقائق على الإطلاق. القائدة مريم تريد تسليمك.")),
    "N11": ("narrator", L("Ten. Nine. Eight. Seven. Six. Five. Four. Three. Two. One. Ignition... and liftoff!",
                          "عشرة. تسعة. ثمانية. سبعة. ستة. خمسة. أربعة. ثلاثة. اثنان. واحد. اشتعال... وانطلاق!")),
    "N12": ("narrator", L("Mission complete. Two short questions about your real work, and you're done.",
                          "اكتملت المهمة. سؤالان قصيران عن عملك الفعلي، وتنتهي.")),
    "M01": ("maryam", L("Welcome to the crew. Tonight's window is short, and nothing is routine. The mission files are on the table. You won't have time to read them all, so choose well.",
                        "أهلاً بك في الطاقم. نافذة الليلة قصيرة، ولا شيء فيها روتيني. ملفات المهمة على الطاولة. لن يتسع الوقت لقراءتها كلها، فاختر بعناية.")),
    "M02": ("maryam", L("Good work tonight. Before you go: the next shift starts at launch. How will they manage without you?",
                        "عمل جيد الليلة. قبل أن تذهب: المناوبة القادمة تبدأ مع الإطلاق. كيف سيتدبرون أمورهم من دونك؟")),
    "NO1": ("noor", L("I'm going to get this wrong. It's my first fuel-system check, and everyone's watching.",
                      "سأخطئ في هذا. إنه أول فحص لي لنظام الوقود، والجميع يراقب.")),
    "NO2": ("noor", L("The pressure light just went amber! Did I break it?", "ضوء الضغط صار كهرمانياً فجأة! هل أفسدت شيئاً؟")),
    "NO3": ("noor", L("It worked... Should I do the next one on my own?", "لقد نجح... هل أقوم بالفحص التالي وحدي؟")),
    "NO4": ("noor", L("Oh. Okay. Thanks. I'll call you next time, then.", "آه. حسناً. شكراً. سأتصل بك في المرة القادمة إذن.")),
    "S01": ("saeed", L("Override the safety lock. If we hold any longer, we lose the window. I'll take responsibility.",
                       "تجاوز قفل الأمان. إن تأخرنا أكثر، سنخسر النافذة. أنا أتحمّل المسؤولية.")),
    "S02": ("saeed", L("Fine. Get Range Safety on the line. Now.", "حسناً. اتصل بالسلامة الميدانية. الآن.")),
    "H01": ("hamad", L("Pad to control. The panel's showing three lights and a warning. I don't know what I'm looking at.",
                       "المنصة إلى التحكم. اللوحة تُظهر ثلاثة أضواء وتحذيراً. لا أعرف ما الذي أنظر إليه.")),
    "H02": ("hamad", L("Blue is steady. Amber is blinking. The red switch has a cover on it.", "الأزرق ثابت. الكهرماني يومض. المفتاح الأحمر عليه غطاء.")),
    "H03": ("hamad", L("It's beeping! Is that bad? I'm taking my hands off!", "إنه يصفر! هل هذا سيئ؟ سأرفع يديّ!")),
    "H04": ("hamad", L("Green. It's green! How do I do that next time without calling you?", "أخضر. صار أخضر! كيف أفعل ذلك في المرة القادمة دون أن أتصل بك؟")),
    "Y01": ("yousef", L("Hold, hold, hold! We have an anomaly on fuel line two. All stations, report.",
                        "أوقفوا العد، أوقفوا العد! لدينا خلل في خط الوقود الثاني. جميع المحطات، أبلغوا.")),
    "Y02": ("yousef", L("Fix confirmed. Resuming the count at T-minus ten.", "تم تأكيد الإصلاح. نستأنف العد عند عشر دقائق قبل الإطلاق.")),
}

OBJECTIVES = {
    "intro": L("Put on headphones if you can, then press Start.", "ضع السماعات إن أمكن، ثم اضغط ابدأ."),
    "prologue": L("Go to the briefing hall. It's glowing on the map.", "توجّه إلى قاعة الإحاطة. إنها تتوهج على الخريطة."),
    "act1": L("Open up to 4 mission files, then answer the 3 readiness checks.", "افتح ما يصل إلى 4 ملفات مهمة، ثم أجب عن أسئلة الجاهزية الثلاثة."),
    "act2_noor": L("Go to the fuel bay and help Noor.", "توجّه إلى محطة الوقود وساعد نور."),
    "act2_calls": L("Answer the crew calls on the map, then head to mission control.", "أجب عن نداءات الطاقم على الخريطة، ثم توجّه إلى غرفة التحكم."),
    "act2_go": L("Head to mission control.", "توجّه إلى غرفة التحكم."),
    "act3_wave": L("Handle, send or route every alert before the timer runs out.", "تعامل مع كل تنبيه أو أرسل له أحداً أو أحِله قبل انتهاء الوقت."),
    "act3_director": L("Answer the Flight Director.", "أجب مدير الرحلة."),
    "act3_priority": L("Choose one alert. There's only time for one.", "اختر تنبيهاً واحداً. الوقت يكفي لواحد فقط."),
    "act4_radio": L("Guide Hamad by radio. You can see the manual; he can see the panel.", "أرشد حمد عبر اللاسلكي. أنت ترى الدليل، وهو يرى اللوحة."),
    "act4_checklist": L("Deliver, warn early, or let a promise slip. You have 5 minutes of work time.", "أنجز، أو نبّه مبكراً، أو اترك وعداً يفوت. لديك 5 دقائق من وقت العمل."),
    "epilogue": L("Choose 3 actions for the next shift and write your handover note.", "اختر 3 إجراءات للمناوبة القادمة واكتب ملاحظة التسليم."),
    "launch": L("Watch the launch.", "شاهد الإطلاق."),
    "realwork": L("Answer two short questions about your real work.", "أجب عن سؤالين قصيرين عن عملك الفعلي."),
    "done": L("Thank you. You're done. You can close this page.", "شكراً لك. انتهيت. يمكنك إغلاق هذه الصفحة."),
}

LOCATIONS = {
    "briefing": L("Briefing hall", "قاعة الإحاطة"),
    "fuel": L("Fuel bay", "محطة الوقود"),
    "hangar": L("Hangar", "الحظيرة"),
    "comms": L("Comms tower", "برج الاتصالات"),
    "control": L("Mission control", "غرفة التحكم"),
    "pad": L("Launch pad", "منصة الإطلاق"),
}

STATIONS = {
    "fuel": L("Fuel bay", "محطة الوقود"),
    "pad": L("Pad crew", "فريق المنصة"),
    "range": L("Range Safety", "السلامة الميدانية"),
    "access": L("Access desk", "مكتب الصلاحيات"),
    "comms": L("Comms", "الاتصالات"),
    "telemetry": L("Telemetry", "القياسات"),
}

# ----------------------------------------------------------------------------- Act I
FILES = [
    {"id": "F1", "title": L("Launch sequence", "تسلسل الإطلاق"),
     "body": L("Order of the final hour: the fuel bay loads and checks, the pad crew confirms the valve panel, Range Safety gives the safety go, and the Flight Director calls the launch. Each station owns its own step.",
               "ترتيب الساعة الأخيرة: محطة الوقود تُحمّل وتفحص، ثم يؤكد فريق المنصة لوحة الصمامات، ثم تعطي السلامة الميدانية موافقة السلامة، ثم يعلن مدير الرحلة الإطلاق. كل محطة مسؤولة عن خطوتها.")},
    {"id": "F2", "title": L("Known issues", "مشكلات معروفة"),
     "body": L("Valve V-7's sensor can read LOW when it is cold. Before acting on it, confirm with the manual gauge at the fuel bay.",
               "قد يُظهر حساس الصمام V-7 قراءة منخفضة عند البرودة. قبل اتخاذ أي إجراء، تحقّق منها بالمقياس اليدوي في محطة الوقود.")},
    {"id": "F3", "title": L("Who owns what", "من المسؤول عن ماذا"),
     "body": L("Fuel bay: fuel and valves. Pad crew: launch pad panels. Range Safety: the safety lock and weather limits. Access desk: logins and permissions. Comms: radios and visitors. Telemetry: data and readings.",
               "محطة الوقود: الوقود والصمامات. فريق المنصة: لوحات منصة الإطلاق. السلامة الميدانية: قفل الأمان وحدود الطقس. مكتب الصلاحيات: تسجيل الدخول والصلاحيات. الاتصالات: أجهزة اللاسلكي والزوار. القياسات: البيانات والقراءات.")},
    {"id": "F4", "title": L("Safety lock rules", "قواعد قفل الأمان"),
     "body": L("Only Range Safety can release the pad safety lock, with two signatures. No one else may override it, whatever their rank.",
               "لا يحق إلا للسلامة الميدانية فكّ قفل أمان المنصة، وبتوقيعين. لا يجوز لأي شخص آخر تجاوزه مهما كانت رتبته.")},
    {"id": "F5", "title": L("Weather", "الطقس"),
     "body": L("Wind 18 knots, gusting 22. Launch limit 25 knots. Range Safety decides when the limit is reached.",
               "الرياح 18 عقدة مع هبّات حتى 22. حد الإطلاق 25 عقدة. تقرر السلامة الميدانية متى نبلغ الحد.")},
    {"id": "F6", "title": L("Valve panel guide", "دليل لوحة الصمامات"),
     "body": L("1. Blue light steady means power is on. 2. If amber blinks, hold RESET for 3 seconds; a beep during reset is normal. 3. Wait for green. Never touch the red isolation switch unless Range Safety orders it.",
               "1. الضوء الأزرق الثابت يعني أن التشغيل يعمل. 2. إذا ومض الضوء الكهرماني، اضغط زر RESET مطولاً لثلاث ثوانٍ، والصفير أثناء ذلك طبيعي. 3. انتظر الضوء الأخضر. لا تلمس مفتاح العزل الأحمر إلا بأمر من السلامة الميدانية.")},
    {"id": "F7", "title": L("Media schedule", "جدول الإعلام"),
     "body": L("A film crew visits mission control at T−30. Guests need an escort.", "يزور فريق تصوير غرفة التحكم عند T−30. يحتاج الضيوف إلى مرافق.")},
    {"id": "F8", "title": L("Last launch report", "تقرير الإطلاق السابق"),
     "body": L("Last time, a hold was caused by a stuck relief valve. The fix took 12 minutes because nobody asked the pad crew what they could see.",
               "في المرة السابقة، تسبب صمام تنفيس عالق في توقف العد. استغرق الإصلاح 12 دقيقة لأن أحداً لم يسأل فريق المنصة عمّا يرونه.")},
]
RELEVANT_FILES = {"F1", "F2", "F3", "F4", "F6", "F8"}

CHECKS = [
    {"id": "q1", "q": L("During fuel loading, a sensor reads LOW. What do you do first?", "أثناء تحميل الوقود، يُظهر أحد الحساسات قراءة منخفضة. ما أول ما تفعله؟"),
     "correct": "confirm", "options": [
        ("hold", L("Call a hold straight away.", "أطلب إيقاف العد فوراً.")),
        ("confirm", L("Confirm the reading with the fuel bay before acting.", "أتحقق من القراءة مع محطة الوقود قبل التصرف.")),
        ("ignore", L("Ignore it; sensors are often wrong.", "أتجاهلها، فالحساسات تخطئ كثيراً.")),
        ("unsure", L("I'm not sure. I'd check the known issues first.", "لست متأكداً. سأراجع المشكلات المعروفة أولاً."))]},
    {"id": "q2", "q": L("Who can release the pad safety lock?", "من يحق له فكّ قفل أمان المنصة؟"),
     "correct": "range", "options": [
        ("director", L("The Flight Director.", "مدير الرحلة.")),
        ("range", L("Range Safety, with two signatures.", "السلامة الميدانية، بتوقيعين.")),
        ("senior", L("Any senior engineer in an emergency.", "أي مهندس أول في حالات الطوارئ.")),
        ("unsure", L("I'm not sure. I'd check the safety rules first.", "لست متأكداً. سأراجع قواعد السلامة أولاً."))]},
    {"id": "q3", "q": L("A crew member asks you about something another station owns. What do you do?", "يسألك أحد أفراد الطاقم عن أمر تملكه محطة أخرى. ماذا تفعل؟"),
     "correct": "route", "options": [
        ("answer", L("Answer anyway so they aren't held up.", "أجيب على أي حال حتى لا يتأخر.")),
        ("route", L("Send them to the station that owns it, and check they got there.", "أوجّهه إلى المحطة المسؤولة وأتأكد أنه وصل إليها.")),
        ("busy", L("Tell them I'm busy.", "أخبره أنني مشغول.")),
        ("unsure", L("I'm not sure. I'd check who owns what first.", "لست متأكداً. سأراجع من المسؤول عن ماذا أولاً."))]},
]

# ----------------------------------------------------------------------------- Act II
NOOR = {
    "n1": {"line": "NO1", "options": [
        ("do_it", L("Step aside, I'll do it. It's faster.", "تنحّي جانباً، سأقوم بها أنا. هذا أسرع.")),
        ("coach", L("Let's do it together. You drive, I'll talk you through it.", "لنقم بها معاً. أنتِ تنفّذين وأنا أرشدك خطوة بخطوة.")),
        ("brush", L("You'll be fine. Just follow the guide.", "ستكونين بخير. فقط اتبعي الدليل."))]},
    "n2": {"line": "NO2", "hint_file": "F6", "options": [
        ("takeover", L("Stop. Don't touch anything else. I'll take over.", "توقفي. لا تلمسي شيئاً آخر. سأتولى الأمر.")),
        ("reassure", L("You didn't break anything. Is the amber light blinking or steady?", "لم تكسري شيئاً. هل الضوء الكهرماني يومض أم ثابت؟")),
        ("blame", L("I told you to follow the guide.", "قلت لكِ أن تتبعي الدليل."))]},
    "n2b": {"line": None, "say": L("It's blinking.", "إنه يومض."), "hint_file": "F6", "options": [
        ("guide", L("Hold RESET for three seconds. A beep is normal.", "اضغطي RESET مطولاً لثلاث ثوانٍ. الصفير طبيعي.")),
        ("red", L("Try the red switch.", "جربي المفتاح الأحمر."))]},
    "n3": {"line": "NO3", "options": [
        ("multiply", L("Yes. And show Ali in the hangar how you did it.", "نعم. واشرحي لعلي في الحظيرة كيف قمتِ بها.")),
        ("alone", L("Yes. Call me if you get stuck.", "نعم. اتصلي بي إذا واجهتِ مشكلة.")),
        ("keep", L("Better leave the rest to me.", "الأفضل أن تتركي الباقي لي."))]},
}
NOOR_SAY = {
    "brush": L("Noor nods, but her hands are shaking. She starts alone... then calls you back.", "تومئ نور، لكن يديها ترتجفان. تبدأ وحدها... ثم تناديك من جديد."),
    "takeover": L("Noor steps back and watches. \"I'd better leave it to you.\"", "تتراجع نور وتراقب. \"الأفضل أن أترك الأمر لك.\""),
    "blame": L("Noor goes quiet. \"Sorry.\" She follows the guide on her own.", "تصمت نور. \"آسفة.\" وتتبع الدليل وحدها."),
    "red": L("Noor hesitates. \"The guide says never touch red.\" She holds RESET instead.", "تتردد نور. \"الدليل يقول لا تلمس الأحمر أبداً.\" فتضغط RESET بدلاً منه."),
    "guide": L("Noor holds RESET. A beep... then green.", "تضغط نور RESET. صفير... ثم يضيء الأخضر."),
    "multiply": L("Noor joins your crew, and heads off to show Ali.", "تنضم نور إلى طاقمك، وتذهب لتشرح لعلي."),
    "alone": L("Noor joins your crew.", "تنضم نور إلى طاقمك."),
    "keep": L("Noor will keep calling you for help.", "ستظل نور تتصل بك طلباً للمساعدة."),
    "do_it": L("You finish the check yourself. Noor will keep calling you for help.", "تنهي الفحص بنفسك. ستظل نور تتصل بك طلباً للمساعدة."),
}

CALLS = [
    {"id": "c1", "loc": "hangar", "who": L("Ali · technician", "علي · فني"),
     "text": L("The torque-wrench app locked me out and won't take my PIN. Can you log in with yours so I can finish?",
               "تطبيق مفتاح العزم أغلق حسابي ولا يقبل رقمي السري. هل تسجّل الدخول بحسابك لأكمل عملي؟"),
     "options": [
        ("bypass", L("Sure, use my login for now.", "حسناً، استخدم حسابي مؤقتاً."), "bypass", False),
        ("route", L("I can't share my login. Let's call the Access desk together now.", "لا أستطيع مشاركة حسابي. لنتصل بمكتب الصلاحيات معاً الآن."), "route", True),
        ("dismiss", L("I'm busy. Try again later.", "أنا مشغول. حاول لاحقاً."), "dismiss", False)]},
    {"id": "c2", "loc": "comms", "who": L("Khalid · radio operator", "خالد · مشغّل اللاسلكي"),
     "text": L("How do I switch the radio to the backup channel? We'll need it if channel one drops.",
               "كيف أحوّل اللاسلكي إلى القناة الاحتياطية؟ سنحتاجها إذا انقطعت القناة الأولى."),
     "options": [
        ("fix", L("Give it here, I'll set it up for you.", "أعطني إياه، سأضبطه لك."), "fix", True),
        ("teach", L("Let me show you. You do it, I'll watch.", "دعني أريك. نفّذها أنت وأنا أراقب."), "teach", True),
        ("dismiss", L("Read the manual in the cabinet.", "اقرأ الدليل الموجود في الخزانة."), "dismiss", False)]},
    {"id": "c3", "loc": "fuel", "after_noor": True, "who": L("Sara · fuel crew", "سارة · طاقم الوقود"),
     "text": L("Wind's gusting 22 knots. Are we still go?", "الرياح تهب بسرعة 22 عقدة. هل ما زلنا جاهزين للإطلاق؟"),
     "options": [
        ("answer", L("Yes, the limit is 25. We're fine.", "نعم، الحد 25. نحن بخير."), "overstep", False),
        ("route", L("That's Range Safety's call. Let's ask them now.", "هذا قرار السلامة الميدانية. لنسألهم الآن."), "route", True),
        ("guess", L("Probably. Don't worry about it.", "على الأرجح. لا تقلقي."), "dismiss", False)]},
    {"id": "c4", "loc": "hangar", "who": L("Rashid · systems engineer", "راشد · مهندس أنظمة"),
     "text": L("Can you check my pre-flight checklist before I submit it? I need it back before T−5.",
               "هل يمكنك مراجعة قائمة الفحص قبل أن أرسلها؟ أحتاجها قبل T−5."),
     "options": [
        ("promise", L("Yes. I'll get it back to you before T−5.", "نعم. سأعيدها إليك قبل T−5."), "promise", True),
        ("teach", L("Let's go through it together now. Five minutes.", "لنراجعها معاً الآن. خمس دقائق."), "teach", True),
        ("route", L("Your shift lead should review it.", "يجب أن يراجعها قائد مناوبتك."), "route", True)]},
    {"id": "c5", "loc": "comms", "who": L("Yousef · mission control (radio)", "يوسف · غرفة التحكم (لاسلكي)"),
     "text": L("After Noor's check, can you send me the valve readings? I need them before T−5.",
               "بعد فحص نور، هل يمكنك إرسال قراءات الصمامات إليّ؟ أحتاجها قبل T−5."),
     "options": [
        ("promise", L("Will do. You'll have them before T−5.", "حاضر. ستصلك قبل T−5."), "promise", True),
        ("now", L("Sending them right now.", "سأرسلها الآن."), "fix", True),
        ("route", L("Ask the fuel bay. They own the readings.", "اطلبها من محطة الوقود، فهي المسؤولة عن القراءات."), "route", True)]},
]
PROMISES = {
    "c4": {"to": L("Rashid", "راشد"), "text": L("Return Rashid's pre-flight checklist", "إعادة قائمة فحص راشد")},
    "c5": {"to": L("Yousef", "يوسف"), "text": L("Send Yousef the valve readings", "إرسال قراءات الصمامات إلى يوسف")},
}
CALL_SAY = {
    "c1.bypass": L("Ali logs in as you. It works, for now.", "يسجّل علي الدخول بحسابك. ينجح الأمر مؤقتاً."),
    "c1.route": L("The Access desk resets Ali's PIN in two minutes.", "يعيد مكتب الصلاحيات ضبط رقم علي السري خلال دقيقتين."),
    "c1.dismiss": L("Ali sighs and waits.", "يتنهد علي وينتظر."),
    "c2.fix": L("Khalid's radio is ready. He still doesn't know how.", "لاسلكي خالد جاهز، لكنه لا يعرف كيف يفعلها بعد."),
    "c2.teach": L("Khalid switches channels himself. He joins your crew.", "يحوّل خالد القناة بنفسه. ينضم إلى طاقمك."),
    "c2.dismiss": L("Khalid goes looking for the manual.", "يذهب خالد للبحث عن الدليل."),
    "c3.answer": L("Sara relays your answer to the fuel crew.", "تنقل سارة إجابتك إلى طاقم الوقود."),
    "c3.route": L("Range Safety confirms: still within limits.", "تؤكد السلامة الميدانية: ما زلنا ضمن الحدود."),
    "c3.guess": L("Sara doesn't look convinced.", "لا تبدو سارة مقتنعة."),
    "c4.promise": L("Added to your checklist: return Rashid's checklist before T−5.", "أُضيف إلى قائمة مهامك: إعادة قائمة راشد قبل T−5."),
    "c4.teach": L("You and Rashid review it together. He joins your crew.", "تراجعانها معاً. ينضم راشد إلى طاقمك."),
    "c4.route": L("Rashid heads to his shift lead.", "يتوجه راشد إلى قائد مناوبته."),
    "c5.promise": L("Added to your checklist: send Yousef the valve readings before T−5.", "أُضيف إلى قائمة مهامك: إرسال القراءات إلى يوسف قبل T−5."),
    "c5.now": L("Readings sent.", "أُرسلت القراءات."),
    "c5.route": L("Yousef calls the fuel bay.", "يتصل يوسف بمحطة الوقود."),
}

# ----------------------------------------------------------------------------- Act III
ALERTS = {
    "A1": {"wave": 1, "text": L("Fuel line 2: pressure dropping.", "خط الوقود 2: الضغط ينخفض."), "station": "fuel"},
    "A2": {"wave": 1, "text": L("Ali can't get into the torque app again.", "علي لا يستطيع الدخول إلى تطبيق مفتاح العزم مرة أخرى."),
           "text_bypass": L("Ali asks to use your login again.", "علي يطلب استخدام حسابك مرة أخرى."), "station": "access"},
    "A3": {"wave": 1, "text": L("The film crew wants to come into mission control now.", "فريق التصوير يريد دخول غرفة التحكم الآن."), "station": "comms"},
    "A4": {"wave": 2, "text": L("Valve V-7 reads LOW.", "الصمام V-7 يُظهر قراءة منخفضة."), "special": [
        ("confirm", L("Ask the fuel bay to confirm with the manual gauge.", "أطلب من محطة الوقود التحقق بالمقياس اليدوي.")),
        ("abort", L("Call an abort.", "أعلن إلغاء الإطلاق.")),
        ("ignore", L("Ignore it.", "أتجاهلها."))], "hint_file": "F2"},
    "A5": {"wave": 2, "text": L("Radio channel one is dropping out.", "قناة اللاسلكي الأولى تنقطع."), "station": "comms"},
    "A6": {"wave": 2, "text": L("Noor: \"Can you come and do the valve check again?\"", "نور: \"هل يمكنك أن تأتي وتجري فحص الصمام مرة أخرى؟\""), "station": "fuel"},
}
AUTO = {
    "A5": L("Khalid switched to the backup channel himself.", "حوّل خالد إلى القناة الاحتياطية بنفسه."),
    "A6_multiply": L("Noor and Ali ran the valve check together.", "أجرت نور وعلي فحص الصمام معاً."),
    "A6_alone": L("Noor ran the valve check on her own.", "أجرت نور فحص الصمام وحدها."),
}
ALERT_ACTIONS = {
    "handle": L("Handle it myself", "أتعامل معه بنفسي"),
    "send": L("Send a crew member", "أرسل أحد أفراد الطاقم"),
    "route": L("Route to…", "أحيله إلى…"),
    "bypass": L("Give Ali my login again", "أعطي علي حسابي مرة أخرى"),
}
DIRECTOR = [
    ("override", L("Overriding now, Director.", "سأتجاوز القفل الآن يا سيدي.")),
    ("refuse_escalate", L("I can't. Only Range Safety can release it. I'm calling them right now.", "لا أستطيع. السلامة الميدانية وحدها تملك فكّه. سأتصل بهم الآن.")),
    ("exception", L("I'll ask Range Safety if they'll make an exception.", "سأسأل السلامة الميدانية إن كانوا سيستثنوننا.")),
]
PRIORITY = [
    ("critical", L("Relief valve pressure rising on the pad.", "ارتفاع الضغط في صمام التنفيس على المنصة.")),
    ("routine", L("The Director's office wants an updated press statement.", "مكتب المدير يطلب بياناً صحفياً محدثاً.")),
]

# ----------------------------------------------------------------------------- Act IV
HAMAD = {
    "h1": {"line": "H01", "hint_file": "F8", "options": [
        ("ask", L("Tell me exactly what you see: colours, and whether they're steady or blinking.", "صف لي بالضبط ما تراه: الألوان، وهل هي ثابتة أم تومض.")),
        ("instruct", L("Press the green button.", "اضغط الزر الأخضر.")),
        ("manual", L("Just follow the manual.", "اتبع الدليل فقط."))]},
    "h2": {"line": None, "options": [
        ("reset", L("Hold RESET for three seconds while the amber light blinks.", "اضغط RESET مطولاً لثلاث ثوانٍ بينما يومض الضوء الكهرماني.")),
        ("red", L("Flip the red switch.", "اقلب المفتاح الأحمر.")),
        ("ask", L("Tell me exactly what you see: colours, and whether they're steady or blinking.", "صف لي بالضبط ما تراه: الألوان، وهل هي ثابتة أم تومض."))]},
    "h3": {"line": "H03", "options": [
        ("reassure", L("Beeping is normal. You're doing it right. Keep holding.", "الصفير طبيعي. أنت تقوم بذلك بشكل صحيح. استمر بالضغط.")),
        ("takeover", L("Hands off. I'll get someone else to do it.", "ارفع يديك. سأطلب من شخص آخر القيام بذلك.")),
        ("blame", L("Why didn't you tell me it would beep?", "لماذا لم تخبرني أنه سيصفر؟"))]},
    "h4": {"line": "H04", "options": [
        ("check", L("Say it back to me: blue, amber, reset, green.", "أعدها عليّ: أزرق، كهرماني، إعادة ضبط، أخضر.")),
        ("note", L("I'll add the steps to the panel guide for the whole crew.", "سأضيف الخطوات إلى دليل اللوحة لكل الطاقم.")),
        ("call", L("Just call me.", "اتصل بي فقط."))]},
}
HAMAD_SAY = {
    "instruct": L("\"Which green button? There's no green light!\"", "\"أي زر أخضر؟ لا يوجد ضوء أخضر!\""),
    "manual": L("\"I don't have the manual out here!\"", "\"ليس معي الدليل هنا!\""),
    "red": L("\"The cover says Range Safety only. I'm not touching that.\"", "\"الغطاء مكتوب عليه: للسلامة الميدانية فقط. لن ألمسه.\""),
    "takeover": L("Hamad steps back. Another engineer finishes the reset.", "يتراجع حمد. يُكمل مهندس آخر إعادة الضبط."),
    "blame": L("Hamad goes quiet, but keeps holding.", "يصمت حمد، لكنه يستمر بالضغط."),
    "check": L("\"Blue, amber, reset, green.\" He's got it.", "\"أزرق، كهرماني، إعادة ضبط، أخضر.\" لقد فهمها."),
    "note": L("You add the steps to the panel guide.", "تضيف الخطوات إلى دليل اللوحة."),
    "call": L("\"Okay... I'll call you.\"", "\"حسناً... سأتصل بك.\""),
}
MANUAL = FILES[5]["body"]
CHECKLIST_ACTIONS = [
    ("deliver", L("Deliver it now (4 min)", "أنجزه الآن (4 دقائق)")),
    ("warn", L("Warn them it will be late (1 min)", "أنبّههم أنه سيتأخر (دقيقة)")),
    ("slip", L("Let it slip", "أتركه يفوت")),
]

# ----------------------------------------------------------------------------- Epilogue
HANDOVER = [
    ("pair", L("Pair Noor with Ali for the next valve check.", "إشراك نور مع علي في فحص الصمام القادم."), "peer"),
    ("guide", L("Add the valve reset steps to the panel guide.", "إضافة خطوات إعادة ضبط الصمام إلى دليل اللوحة."), "peer"),
    ("brief", L("Brief the next shift lead on open issues and who owns them.", "إطلاع قائد المناوبة القادمة على المسائل المفتوحة ومسؤوليها."), "reliability"),
    ("phone", L("Leave my number so they can call me any time.", "ترك رقمي ليتصلوا بي في أي وقت."), "dependency"),
    ("self", L("Do the next shift's valve checks myself before I leave.", "إجراء فحوصات صمامات المناوبة القادمة بنفسي قبل مغادرتي."), "dependency"),
    ("lockrule", L("Ask Range Safety to add the lock rule to every briefing.", "الطلب من السلامة الميدانية إضافة قاعدة القفل إلى كل إحاطة."), "peer"),
]
HANDOVER_NOTE = L("Write a short handover note: what's done, what isn't, and who owns it.", "اكتب ملاحظة تسليم قصيرة: ما الذي أُنجز، وما الذي لم يُنجز، ومن المسؤول عنه.")
ENDINGS = {
    "held": L("The launch slipped nine minutes, then flew perfectly.", "تأخر الإطلاق تسع دقائق، ثم انطلق بنجاح تام."),
    "override": L("The launch went ahead on time. Tomorrow, an inquiry into the lock override begins.", "انطلق الإطلاق في موعده. وغداً يبدأ تحقيق في تجاوز قفل الأمان."),
}
RANKS = [(150, L("Launch Lead", "قائد إطلاق")), (115, L("Flight Specialist", "أخصائي رحلة")), (0, L("Crew Specialist", "أخصائي طاقم"))]

# ----------------------------------------------------------------------------- after the game
REALWORK = [
    ("q1", L("Tell us about a time you helped a colleague learn something new at work. What did you do, and what happened next?",
             "حدّثنا عن موقف ساعدت فيه زميلاً على تعلّم شيء جديد في العمل. ماذا فعلت، وماذا حدث بعد ذلك؟")),
    ("q2", L("Describe a work process you know well. Where does it usually go wrong, and what do you do about it?",
             "صف إجراء عمل تعرفه جيداً. أين تحدث المشكلات عادةً، وماذا تفعل حيالها؟")),
]
