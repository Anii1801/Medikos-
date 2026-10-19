"""Clinical history ontology + adaptive dialogue manager + red-flag engine."""
from __future__ import annotations
from typing import Callable, Optional

def _o(*pairs):  # "English|हिंदी"
    return [{"v": p.split("|")[0], "en": p.split("|")[0], "hi": p.split("|")[1]} for p in pairs]

def Q(id, sec, typ, en, hi, opts=None, when: Optional[Callable] = None):
    return {"id": id, "section": sec, "type": typ, "en": en, "hi": hi, "options": opts or [], "when": when}

CC = _o("Chest pain|छाती में दर्द", "Fever|बुखार", "Cough / breathlessness|खांसी / सांस फूलना",
        "Stomach pain|पेट दर्द", "Headache|सिर दर्द", "Joint / back pain|जोड़ / कमर दर्द",
        "Weakness / tiredness|कमज़ोरी", "Other|अन्य")
NONE = "None|कुछ नहीं"
is_cc = lambda c: (lambda a: a.get("cc") == c)
AY = lambda a: bool(a.get("_ay"))

QUESTIONS = [
 Q("cc", "Chief complaint", "single", "What is your main problem today?", "आज आपकी मुख्य समस्या क्या है?", CC),
 Q("cc_text", "Chief complaint", "text", "Please describe it in your own words.", "कृपया अपने शब्दों में बताइए।", when=is_cc("Other")),
 Q("dur", "HPI", "single", "Since when?", "कब से?", _o("Today|आज", "Few days|कुछ दिन", "1–4 weeks|1–4 हफ़्ते", "Months|महीनों से")),
 Q("sev", "HPI", "single", "How bad is it?", "कितनी तकलीफ़ है?", _o("Mild|हल्की", "Moderate|मध्यम", "Severe|बहुत ज़्यादा")),
 Q("progression", "HPI", "single", "Is it getting better, worse, or staying the same?", "क्या यह बेहतर, बदतर या वैसा ही हो रहा है?",
   _o("Getting better|बेहतर हो रहा है", "Getting worse|बदतर हो रहा है", "Comes and goes|आता-जाता है", "Same|वैसा ही है")),
 Q("cp_site", "SOCRATES", "single", "Where exactly is the pain?", "दर्द ठीक कहाँ है?",
   _o("Centre of chest|छाती के बीच", "Left side|बायीं ओर", "Sharp, one spot|एक जगह तेज़"), is_cc("Chest pain")),
 Q("cp_char", "SOCRATES", "single", "What does it feel like?", "दर्द कैसा लगता है?",
   _o("Pressure / heaviness|दबाव / भारीपन", "Stabbing|चुभन", "Burning|जलन"), is_cc("Chest pain")),
 Q("cp_rad", "SOCRATES", "single", "Does it spread anywhere?", "क्या दर्द कहीं फैलता है?",
   _o("Arm / jaw / back|बाँह / जबड़ा / पीठ", "No spread|नहीं फैलता"), is_cc("Chest pain")),
 Q("cp_agg", "SOCRATES", "single", "What makes it worse or better?", "किससे बढ़ता या घटता है?",
   _o("Worse on walking / effort|चलने से बढ़ता है", "Worse on deep breath|गहरी सांस से बढ़ता है",
      "Worse after food, better with antacid|खाने के बाद बढ़ता है", "Nothing changes it|कुछ असर नहीं"), is_cc("Chest pain")),
 Q("fv_pat", "HPI (fever)", "single", "How is the fever?", "बुखार कैसा है?",
   _o("Continuous|लगातार", "Comes and goes with chills|ठंड के साथ आता-जाता", "Only evenings|सिर्फ़ शाम को"), is_cc("Fever")),
 Q("fv_exp", "HPI (fever)", "multi", "Any of these?", "इनमें से कुछ?",
   _o("Rash|दाने", "Body ache / joint pain|बदन दर्द", "Mosquito exposure / travel|मच्छर / यात्रा", "Burning urine|पेशाब में जलन", NONE), is_cc("Fever")),
 Q("co_type", "HPI (respiratory)", "single", "What kind of cough?", "कैसी खांसी?",
   _o("Dry|सूखी", "With phlegm|बलगम के साथ", "With blood|खून के साथ", "Mostly breathlessness|ज़्यादातर सांस फूलना"), is_cc("Cough / breathlessness")),
 Q("co_night", "HPI (respiratory)", "multi", "Any of these?", "इनमें से कुछ?",
   _o("Night sweats|रात को पसीना", "Weight loss|वज़न घटना", "Wheeze|घरघराहट", "Cough > 2 weeks|2 हफ़्ते से ज़्यादा खांसी", NONE), is_cc("Cough / breathlessness")),
 Q("st_loc", "HPI (abdomen)", "single", "Where is the pain?", "दर्द कहाँ है?",
   _o("Upper middle|ऊपर बीच में", "Right lower|दायें नीचे", "Lower abdomen|पेट के नीचे", "All over|पूरे पेट में"), is_cc("Stomach pain")),
 Q("st_rel", "HPI (abdomen)", "multi", "Any of these?", "इनमें से कुछ?",
   _o("Worse after eating|खाने के बाद बढ़ना", "Vomiting|उल्टी", "Black stools / blood in stool|काला मल / खून", "Loose motions|दस्त", "Constipation|कब्ज़", NONE), is_cc("Stomach pain")),
 Q("ha_type", "HPI (headache)", "single", "Describe the headache", "सिर दर्द कैसा है?",
   _o("Sudden, worst ever|अचानक, सबसे तेज़", "One-sided, throbbing|एक तरफ़, धड़कता", "Band-like, tight|कसा हुआ", "Gradual, daily|धीरे-धीरे, रोज़"), is_cc("Headache")),
 Q("ha_assoc", "HPI (headache)", "multi", "Any of these?", "इनमें से कुछ?",
   _o("Vomiting|उल्टी", "Blurred vision|धुंधला दिखना", "Neck stiffness|गर्दन अकड़ना", "Light sensitivity|रोशनी से तकलीफ़", NONE), is_cc("Headache")),
 Q("jt_site", "HPI (musculoskeletal)", "multi", "Which areas?", "कौन सी जगह?",
   _o("Knees|घुटने", "Hands / small joints|हाथ / छोटे जोड़", "Lower back|कमर", "Neck / shoulder|गर्दन / कंधा", "Hips|कूल्हे"), is_cc("Joint / back pain")),
 Q("jt_stiff", "HPI (musculoskeletal)", "single", "Morning stiffness?", "सुबह अकड़न?",
   _o("More than 1 hour|1 घंटे से ज़्यादा", "Less than 30 min|30 मिनट से कम", "No stiffness|नहीं"), is_cc("Joint / back pain")),
 Q("assoc", "Associated symptoms", "multi", "Any of these as well?", "इनमें से कुछ और?",
   _o("Breathlessness|सांस फूलना", "Sweating|पसीना", "Vomiting|उल्टी", "Dizziness / fainting|चक्कर / बेहोशी",
      "Weakness of face/arm/leg|चेहरे/हाथ/पैर में कमज़ोरी", "Weight loss|वज़न घटना", NONE)),
 Q("pmh", "Past medical / surgical", "multi", "Do you have any of these?", "क्या आपको इनमें से कोई है?",
   _o("Diabetes|मधुमेह", "High BP|उच्च रक्तचाप", "Heart disease|हृदय रोग", "Asthma / TB|दमा / टीबी",
      "Kidney disease|गुर्दे की बीमारी", "Thyroid|थायरॉइड", "Past surgery|पहले ऑपरेशन", NONE)),
 Q("meds", "Drugs", "text", "Which medicines do you take now? (name and dose if known)", "अभी आप कौन सी दवाएँ लेते हैं?"),
 Q("allergy", "Allergy", "text", "Are you allergic to any medicine or food?", "क्या किसी दवा या खाने से एलर्जी है?"),
 Q("fam", "Family history", "multi", "Anyone in your family with:", "परिवार में किसी को:",
   _o("Diabetes|मधुमेह", "Heart disease|हृदय रोग", "Cancer|कैंसर", "High BP|उच्च रक्तचाप", "Stroke|लकवा", NONE)),
 Q("pers", "Personal history", "multi", "Your habits", "आपकी आदतें",
   _o("Smoking / tobacco|तंबाकू", "Alcohol|शराब", "Poor sleep|कम नींद", "Irregular meals|अनियमित भोजन", NONE)),
 Q("ros", "Review of systems", "multi", "In the last month, have you had:", "पिछले महीने क्या हुआ:",
   _o("Fever|बुखार", "Cough|खांसी", "Burning urine|पेशाब में जलन", "Blood in urine|पेशाब में खून", "Palpitations|धड़कन तेज़",
      "Swelling of feet|पैरों में सूजन", "Excess thirst / urination|ज़्यादा प्यास / पेशाब", NONE)),
 Q("ay_prak", "Prakriti", "single", "Your body type feels most like:", "आपका शरीर किस जैसा है?",
   _o("Thin, dry, restless (Vata)|दुबला, रूखा, चंचल (वात)", "Medium, warm, sharp (Pitta)|मध्यम, गर्म, तीव्र (पित्त)", "Sturdy, calm, slow (Kapha)|मज़बूत, शांत, धीमा (कफ)"), AY),
 Q("ay_vik", "Vikriti", "single", "Which has increased lately?", "हाल में क्या बढ़ा है?",
   _o("Dryness, gas, anxiety (Vata)|रूखापन, गैस, घबराहट (वात)", "Heat, acidity, anger (Pitta)|गर्मी, अम्लता, गुस्सा (पित्त)", "Heaviness, mucus, lethargy (Kapha)|भारीपन, बलगम, सुस्ती (कफ)"), AY),
 Q("ay_sara", "Sara (tissue quality)", "single", "Skin, hair and nails are mostly:", "त्वचा, बाल, नाखून:",
   _o("Dry, brittle|रूखे, भंगुर", "Soft, oily, early greying|मुलायम, तैलीय", "Thick, lustrous|घने, चमकदार"), AY),
 Q("ay_sam", "Samhanana (build)", "single", "Body frame:", "शरीर का ढांचा:", _o("Light, slender|हल्का, पतला", "Moderate|मध्यम", "Well built, compact|सुगठित"), AY),
 Q("ay_pram", "Pramana (measure)", "single", "Height / weight for age:", "उम्र के हिसाब से कद/वज़न:", _o("Under|कम", "Average|औसत", "Over|ज़्यादा"), AY),
 Q("ay_sat", "Satmya (suitability)", "single", "Foods that suit you best:", "कौन सा भोजन सूट करता है:",
   _o("Warm, oily, sweet|गर्म, चिकना, मीठा", "Cool, bitter, astringent|ठंडा, कड़वा, कसैला", "Light, dry, pungent|हल्का, रूखा, तीखा"), AY),
 Q("ay_sattva", "Sattva (mind)", "single", "Mind and temperament:", "मन और स्वभाव:",
   _o("Anxious, easily scared|चिंतित, डरने वाला", "Irritable, ambitious|चिड़चिड़ा, महत्वाकांक्षी", "Calm, steady|शांत, स्थिर"), AY),
 Q("ay_agni", "Agni / Koshtha", "single", "Digestion and bowels:", "पाचन और मल:",
   _o("Irregular hunger, gas, hard stool (Vishama)|अनियमित भूख, गैस, कठोर मल", "Strong hunger, acidity, loose stool (Tikshna)|तेज़ भूख, अम्लता, ढीला मल",
      "Slow digestion, heaviness (Manda)|धीमा पाचन, भारीपन", "Balanced (Sama)|सामान्य"), AY),
 Q("ay_ahar", "Ahara Shakti / Vyayama Shakti", "single", "Appetite and stamina for exercise:", "भूख और व्यायाम क्षमता:",
   _o("Low appetite, tires quickly|कम भूख, जल्दी थकान", "Good appetite, moderate stamina|अच्छी भूख, मध्यम", "Good appetite, high stamina|अच्छी भूख, ज़्यादा सहनशक्ति"), AY),
 Q("ay_vihara", "Ahara-Vihara", "single", "Diet and daily routine:", "खान-पान और दिनचर्या:",
   _o("Vegetarian, regular routine|शाकाहारी, नियमित", "Vegetarian, irregular routine|शाकाहारी, अनियमित", "Mixed diet, regular|मिश्रित, नियमित", "Mixed diet, irregular|मिश्रित, अनियमित"), AY),
 Q("free", "Patient's own words", "text", "Anything else you want the doctor to know?", "डॉक्टर को और कुछ बताना है?"),
]
BY_ID = {q["id"]: q for q in QUESTIONS}

def applicable(answers: dict) -> list[dict]:
    return [q for q in QUESTIONS if q["when"] is None or q["when"](answers)]

def public(q: dict) -> dict:
    return {k: v for k, v in q.items() if k != "when"}

def next_question(answers: dict) -> dict:
    plan = applicable(answers)
    todo = [q for q in plan if q["id"] not in answers]
    return {"question": public(todo[0]) if todo else None, "answered": len(plan) - len(todo), "total": len(plan),
            "complete": not todo, "red_flags": red_flags(answers)}

def red_flags(a: dict) -> list[dict]:
    from .redflag_engine import evaluate_legacy
    return evaluate_legacy(a)
