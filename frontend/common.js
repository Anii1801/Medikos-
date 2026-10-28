const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const PATIENT_I18N = {
  en: {
    welcome: "Your health, in one place.", sub: "Complete your medical history and organize your reports before your consultation.",
    quick: "Continue as guest", login: "Log in", reg: "Register",
    user: "Username", pw: "Password", name: "Your name", age: "Age", abha: "ABHA ID (optional)",
    ayush: "Ayurveda OPD — extended Dashavidha Pariksha history",
    consentH: "Privacy and consent", c1: "I consent to my health information being recorded for my doctor.",
    start: "Start Interview", cont: "Continue Interview", next: "Continue", back: "Back", speak: "Speak", listen: "Listening…",
    type: "Type or speak your answer", docsH: "Upload medical reports",
    docsS: "Upload prescriptions, laboratory reports, and other medical documents.",
    addDoc: "Browse files", upload: "Upload", or: "or type the report text manually", add: "Add text",
    date: "Report date (YYYY-MM-DD)", sumH: "My health summary",
    sumS: "Review your recorded history and the latest generated draft. Your clinician will also review it.",
    send: "Send to doctor", done: "Submitted", dash: "Health timeline", out: "Log out",
    erase: "Delete all my data", nodocs: "No documents uploaded yet.",
    flag: "Urgent finding — staff should be alerted", tokenL: "Your token number",
    wait: "Wait for your turn. Emergency cases are seen first.",
    readMsg: "Uploading and extracting text…",
    manual: "Could not read this file. Type the content below, or try another document.",
    healthSummary: "Recorded encounters", recentVisits: "Recent encounters",
    noRecords: "No encounters recorded yet.", quickActions: "Prepare for your visit",
    newH: "Start Interview", notSure: "Not sure", preferNot: "Prefer not to answer",
    home: "Home", about: "About", patient: "Patient", menu: "Menu", openMenu: "Open workspace menu",
    closeMenu: "Close workspace menu", dashboard: "Dashboard", medicalHistory: "Medical History",
    medicalReports: "Medical Reports", timeline: "Health Timeline", mySummary: "My Summary",
    signOut: "Sign out", returnHome: "Return home", dashboardEyebrow: "PATIENT DASHBOARD",
    welcomeName: "Welcome", prepareConsultation: "Prepare your information before your next consultation.",
    medicalHistoryHelp: "Answer questions about your symptoms, health history, and medications.",
    documentsCount: "uploaded documents", uploadOrganize: "Upload and organize your reports.",
    encountersCount: "recorded encounters.", noEncounters: "No encounters recorded yet.",
    summaryReviewHelp: "Review an available generated draft and its source information.",
    recentActivity: "Recent activity", accountData: "Account data",
    eraseWarning: "You can permanently erase your working data and submitted records from this application. This cannot be undone.",
    confirmErase: "Permanently erase your documents, encounter records, evidence, and account? This cannot be undone.",
    eraseFailed: "Data deletion failed", startInterview: "Start Interview", continueInterview: "Continue Interview",
    completeHistory: "Complete your medical history",
    guidedInterviewHelp: "The guided interview adapts to your answers and preserves your progress.",
    continueYourInterview: "Continue your interview", readyBegin: "Ready to begin?",
    savedSessionReady: "Your saved session is ready to continue.",
    oneQuestionHelp: "Answer one question at a time. You can go back and review your answers.",
    guestContinue: "Continue as guest",
    guestRetention: "Guest working-session data is removed after submission. Encounter evidence and source documents remain attached to the submitted record for clinician review.",
    interfaceLanguage: "Interface language", english: "English", hindi: "Hindi",
    inputMode: "Interview mode", clickMode: "Click/Tap Mode", voiceMode: "Hands-Free Voice Mode",
    clickModeHelp: "Read each question and answer using the buttons or keyboard. Microphone listening stays off.",
    voiceModeHelp: "Questions are spoken and the microphone listens automatically after each question. You can pause or stop at any time.",
    micPermission: "Microphone permission and availability", micNotRequested: "Permission will be requested when you start a voice interview.",
    micSupported: "Speech recognition is available in this browser. Microphone permission is requested when you start.",
    micUnavailable: "Speech recognition is not supported by this browser. Choose Click/Tap Mode.",
    startSelectedMode: "Start Interview", changeMode: "Change interview mode",
    voiceFallback: "Microphone access or speech recognition is unavailable. You can continue in Click/Tap Mode.",
    voiceExplainer: "The interview will listen to spoken answers after each spoken question. Your browser may process speech; original audio is not retained by MediKiosk.",
    voiceStateReady: "Ready", voiceStateSpeaking: "Speaking", voiceStateListening: "Listening",
    voiceStateProcessing: "Processing", voiceStateConfirm: "Confirm answer", voiceStatePaused: "Paused",
    voiceStateError: "Error", repeatQuestion: "Repeat question", editAnswer: "Correct answer",
    confirmAnswer: "Confirm answer", pauseInterview: "Pause interview", resumeInterview: "Resume interview",
    stopInterview: "Stop interview", transcriptLabel: "Recognized words — review before saving",
    voiceTryAgain: "Try again", noSpeech: "No speech was detected. The question will be repeated once.",
    unsupportedLanguage: "Speech recognition for the selected language is not available. Switch to Click/Tap Mode; recognition will not switch languages automatically.",
    ttsUnavailable: "No suitable Hindi speech voice is installed. Read the question on screen; answer listening can still continue.",
    voiceCommandPrompt: "Say confirm, correct, repeat, pause, or stop.",
    answerReadback: "I heard", clarificationPrompt: "I could not confidently match that answer. Please choose the intended option or say it again.",
    voiceStateClarification: "Clarification required",
    uploadedDocuments: "Uploaded Documents", unclassified: "Unclassified", extractionFailed: "Automatic text extraction failed. Open the original document and review it manually.",
    extractionPartial: "Extraction is partial or needs review. Verify the extracted findings against the original document.",
    uploadDate: "Uploaded", extractionStatus: "Extraction status", extractionWarning: "Extraction warning",
    sourcePage: "Page", sourceText: "Text", viewDownloadOriginal: "Download original",
    documentCategory: "Document category", saveCategory: "Save category",
    retryExtraction: "Retry extraction", uploaded: "Uploaded", extractionEngine: "Extraction engine",
    documentDate: "Document date", extractedText: "Preview extracted text",
    noExtractedText: "No text was extracted. Verify the original or retry extraction.",
    noFindings: "No laboratory findings were extracted from this document.",
    documentsLoadFailed: "Documents could not be loaded", chooseDocument: "Choose a document",
    uploadReports: "Upload Reports", maxUpload: "Up to 10 files, 8 MiB each and 32 MiB per batch.",
    chooseAtLeastOne: "Choose at least one file.", uploadFailed: "Upload failed",
    processingDocuments: "Processing documents…", retryFailed: "Retry failed",
    categoryUpdated: "Document category updated.", categoryFailed: "Category update failed",
    removeDocument: "Remove document", removeConfirm: "Remove this document from your working list? Submitted encounter copies are not changed.",
    documentRemoved: "Document removed.", removalFailed: "Removal failed",
    documentTimeline: "HEALTH TIMELINE", recordedHistory: "Your recorded history",
    timelineDisclaimer: "Encounter dates and document upload dates are shown separately; an upload date is not a clinical event date.",
    encounter: "Encounter", document: "Document", emergency: "Emergency", urgent: "Urgent",
    routine: "Routine", priority: "Priority", status: "Status", downloadSource: "Download source",
    timelineFailed: "Timeline could not be loaded", documentDownloadFailed: "Document download failed",
    summaryEyebrow: "MY SUMMARY", clinicalSummary: "Clinical summary",
    summaryDisclaimer: "Patient-reported and document-extracted information remain attributed and unresolved conflicts are preserved.",
    submitToCreateSummary: "Complete and submit a medical history interview to create a summary.",
    summaryRecordsFailed: "Summary records could not be loaded",
    latestSummaryFailed: "The latest summary could not be loaded",
    loginEyebrow: "SECURE PATIENT ACCESS", signInOrRegister: "Sign in or register",
    accessHelp: "Access your health timeline, reports, and summaries.",
    signIn: "Sign in", register: "Register", password: "Password", show: "Show", hide: "Hide",
    createAccount: "Create account", homepage: "Return to homepage",
    consentRequired: "Required before the interview begins",
    consentError: "Please consent to recording health information for your doctor before continuing.",
    enterAnswer: "Please select or answer before continuing.",
    modeReady: "Ready to begin", languageSwitch: "Change language",
    sectionChief: "Chief complaint", sectionHpi: "History of present illness",
    sectionSoc: "Symptom questions", sectionAssociated: "Associated symptoms",
    sectionHistory: "Medical history", sectionMedication: "Medications and allergies",
    sectionAyush: "AYUSH assessment", uploadFileLimits: "PDF, JPG, PNG, WEBP, TIFF, or TXT · up to 10 files, 8 MiB each and 32 MiB per batch.",
    typeReportText: "Type the text from your report here.", someDocumentsAttention: "Some documents need attention. Review each file's status.",
    documentsProcessed: "Documents processed.", added: "Added", removeDocumentConfirm: "Remove this document?",
    No: "No", Yes: "Yes", close: "Close"
  },
  hi: {
    welcome: "आपका स्वास्थ्य, एक जगह।", sub: "परामर्श से पहले अपना स्वास्थ्य इतिहास पूरा करें और रिपोर्ट व्यवस्थित करें।",
    quick: "अतिथि के रूप में जारी रखें", login: "लॉग इन", reg: "खाता बनाएँ",
    user: "यूज़रनेम", pw: "पासवर्ड", name: "आपका नाम", age: "उम्र", abha: "आभा आईडी (वैकल्पिक)",
    ayush: "आयुर्वेद ओपीडी — दशविध परीक्षा का विस्तृत इतिहास",
    consentH: "गोपनीयता और सहमति", c1: "मैं डॉक्टर के लिए अपनी स्वास्थ्य जानकारी दर्ज करने की सहमति देता/देती हूँ।",
    start: "साक्षात्कार शुरू करें", cont: "साक्षात्कार जारी रखें", next: "आगे", back: "पीछे",
    speak: "बोलें", listen: "सुन रहा है…", type: "अपना उत्तर लिखें या बोलें",
    docsH: "मेडिकल रिपोर्ट अपलोड करें",
    docsS: "पर्चे, प्रयोगशाला रिपोर्ट और अन्य मेडिकल दस्तावेज़ अपलोड करें।",
    addDoc: "फ़ाइलें चुनें", upload: "अपलोड करें", or: "या रिपोर्ट का पाठ लिखें", add: "पाठ जोड़ें",
    date: "रिपोर्ट की तारीख (YYYY-MM-DD)", sumH: "मेरे स्वास्थ्य का सारांश",
    sumS: "दर्ज इतिहास और नया मसौदा देखें। आपका चिकित्सक भी इसकी समीक्षा करेगा।",
    send: "डॉक्टर को भेजें", done: "जमा हो गया", dash: "स्वास्थ्य समयरेखा", out: "लॉग आउट",
    erase: "मेरा पूरा डेटा मिटाएँ", nodocs: "कोई दस्तावेज़ अपलोड नहीं है।",
    flag: "तत्काल ध्यान देने योग्य जानकारी — कर्मचारियों को सूचित करें",
    tokenL: "आपका टोकन नंबर", wait: "अपनी बारी की प्रतीक्षा करें। आपातकालीन मामलों को पहले देखा जाता है।",
    readMsg: "अपलोड हो रहा है और पाठ निकाला जा रहा है…",
    manual: "इस फ़ाइल को पढ़ा नहीं जा सका। नीचे इसकी सामग्री लिखें या दूसरा दस्तावेज़ आज़माएँ।",
    healthSummary: "दर्ज मुलाकातें", recentVisits: "हाल की मुलाकातें",
    noRecords: "अभी तक कोई मुलाकात दर्ज नहीं है।", quickActions: "अपनी मुलाकात की तैयारी करें",
    newH: "साक्षात्कार शुरू करें", notSure: "पता नहीं", preferNot: "उत्तर नहीं देना चाहते",
    home: "होम", about: "परिचय", patient: "मरीज़", menu: "मेनू",
    openMenu: "कार्यस्थल मेनू खोलें", closeMenu: "कार्यस्थल मेनू बंद करें",
    dashboard: "डैशबोर्ड", medicalHistory: "स्वास्थ्य इतिहास", medicalReports: "मेडिकल रिपोर्ट",
    timeline: "स्वास्थ्य समयरेखा", mySummary: "मेरा सारांश", signOut: "लॉग आउट",
    returnHome: "होम पर लौटें", dashboardEyebrow: "मरीज़ का डैशबोर्ड",
    welcomeName: "स्वागत है", prepareConsultation: "अगली परामर्श मुलाकात से पहले अपनी जानकारी तैयार करें।",
    medicalHistoryHelp: "लक्षणों, स्वास्थ्य इतिहास और दवाओं के बारे में उत्तर दें।",
    documentsCount: "अपलोड किए गए दस्तावेज़", uploadOrganize: "अपनी रिपोर्ट अपलोड करें और व्यवस्थित करें।",
    encountersCount: "दर्ज मुलाकातें।", noEncounters: "अभी तक कोई मुलाकात दर्ज नहीं है।",
    summaryReviewHelp: "उपलब्ध मसौदे और उसके स्रोत की जानकारी देखें।",
    recentActivity: "हाल की गतिविधि", accountData: "खाते का डेटा",
    eraseWarning: "आप इस ऐप से अपना काम का डेटा और जमा किए गए रिकॉर्ड स्थायी रूप से मिटा सकते हैं। इसे वापस नहीं किया जा सकता।",
    confirmErase: "क्या आप अपने दस्तावेज़, मुलाकात के रिकॉर्ड, साक्ष्य और खाता स्थायी रूप से मिटाना चाहते हैं? इसे वापस नहीं किया जा सकता।",
    eraseFailed: "डेटा मिटाया नहीं जा सका", startInterview: "साक्षात्कार शुरू करें",
    continueInterview: "साक्षात्कार जारी रखें", completeHistory: "अपना स्वास्थ्य इतिहास पूरा करें",
    guidedInterviewHelp: "यह साक्षात्कार आपके उत्तरों के अनुसार आगे बढ़ता है और आपकी प्रगति सुरक्षित रखता है।",
    continueYourInterview: "साक्षात्कार जारी रखें", readyBegin: "शुरू करने के लिए तैयार हैं?",
    savedSessionReady: "आपका सहेजा हुआ सत्र जारी रखने के लिए तैयार है।",
    oneQuestionHelp: "एक बार में एक प्रश्न का उत्तर दें। आप पीछे जाकर उत्तर देख सकते हैं।",
    guestContinue: "अतिथि के रूप में जारी रखें",
    guestRetention: "जमा करने के बाद अतिथि सत्र का अस्थायी डेटा हटा दिया जाता है। मुलाकात के साक्ष्य और मूल दस्तावेज़ चिकित्सक की समीक्षा के लिए जमा रिकॉर्ड से जुड़े रहते हैं।",
    interfaceLanguage: "इंटरफ़ेस की भाषा", english: "अंग्रेज़ी", hindi: "हिंदी",
    inputMode: "साक्षात्कार का तरीका", clickMode: "क्लिक/टैप तरीका", voiceMode: "हाथों से मुक्त आवाज़ का तरीका",
    clickModeHelp: "हर प्रश्न पढ़ें और बटन या कीबोर्ड से उत्तर दें। माइक्रोफ़ोन नहीं सुनेगा।",
    voiceModeHelp: "प्रश्न आवाज़ में सुनाए जाएँगे और हर प्रश्न के बाद माइक्रोफ़ोन अपने-आप सुनेगा। आप कभी भी रोक सकते हैं।",
    micPermission: "माइक्रोफ़ोन की अनुमति और उपलब्धता",
    micNotRequested: "आवाज़ वाला साक्षात्कार शुरू करते समय अनुमति माँगी जाएगी।",
    micSupported: "इस ब्राउज़र में वाक् पहचान उपलब्ध है। शुरू करते समय माइक्रोफ़ोन की अनुमति माँगी जाएगी।",
    micUnavailable: "इस ब्राउज़र में वाक् पहचान उपलब्ध नहीं है। क्लिक/टैप तरीका चुनें।",
    startSelectedMode: "साक्षात्कार शुरू करें", changeMode: "साक्षात्कार का तरीका बदलें",
    voiceFallback: "माइक्रोफ़ोन या वाक् पहचान उपलब्ध नहीं है। आप क्लिक/टैप तरीके से जारी रख सकते हैं।",
    voiceExplainer: "हर बोले गए प्रश्न के बाद साक्षात्कार आपके उत्तर सुनेगा। आपका ब्राउज़र आवाज़ संसाधित कर सकता है; MediKiosk मूल ऑडियो सहेजता नहीं है।",
    voiceStateReady: "तैयार", voiceStateSpeaking: "बोल रहा है", voiceStateListening: "सुन रहा है",
    voiceStateProcessing: "प्रक्रिया जारी है", voiceStateConfirm: "उत्तर की पुष्टि करें",
    voiceStatePaused: "रुका हुआ", voiceStateError: "त्रुटि",
    repeatQuestion: "प्रश्न दोहराएँ", editAnswer: "उत्तर सुधारें", confirmAnswer: "उत्तर की पुष्टि करें",
    pauseInterview: "साक्षात्कार रोकें", resumeInterview: "साक्षात्कार फिर शुरू करें",
    stopInterview: "साक्षात्कार बंद करें", transcriptLabel: "पहचाने गए शब्द — सहेजने से पहले जाँचें",
    voiceTryAgain: "फिर कोशिश करें", noSpeech: "आवाज़ नहीं मिली। प्रश्न एक बार फिर सुनाया जाएगा।",
    unsupportedLanguage: "चुनी हुई भाषा के लिए वाक् पहचान उपलब्ध नहीं है। क्लिक/टैप तरीका चुनें; पहचान भाषा अपने-आप नहीं बदलेगी।",
    ttsUnavailable: "हिंदी बोलने वाली उपयुक्त आवाज़ उपलब्ध नहीं है। प्रश्न स्क्रीन पर पढ़ें; उत्तर सुनना जारी रह सकता है।",
    voiceCommandPrompt: "पुष्टि, सुधार, दोहराएँ, रोकें या बंद करें कहें।",
    answerReadback: "मैंने यह सुना", clarificationPrompt: "उत्तर किसी विकल्प से स्पष्ट रूप से मेल नहीं खाता। सही विकल्प चुनें या फिर से बोलें।",
    voiceStateClarification: "स्पष्टीकरण आवश्यक",
    uploadedDocuments: "अपलोड किए गए दस्तावेज़", unclassified: "वर्गीकृत नहीं",
    extractionFailed: "पाठ अपने-आप नहीं निकाला जा सका। मूल दस्तावेज़ खोलकर स्वयं जाँचें।",
    extractionPartial: "पाठ का कुछ हिस्सा निकला है या समीक्षा आवश्यक है। मूल दस्तावेज़ से निकली जानकारी की पुष्टि करें।",
    uploadDate: "अपलोड की तारीख", extractionStatus: "पाठ निकालने की स्थिति",
    extractionWarning: "पाठ निकालने की चेतावनी", sourcePage: "पृष्ठ", sourceText: "पाठ",
    viewDownloadOriginal: "मूल दस्तावेज़ डाउनलोड करें", documentCategory: "दस्तावेज़ का प्रकार",
    saveCategory: "प्रकार सहेजें", retryExtraction: "पाठ फिर से निकालें", uploaded: "अपलोड हुआ",
    extractionEngine: "पाठ निकालने का माध्यम", documentDate: "दस्तावेज़ की तारीख",
    extractedText: "निकाला गया पाठ देखें",
    noExtractedText: "कोई पाठ नहीं निकला। मूल दस्तावेज़ जाँचें या फिर से कोशिश करें।",
    noFindings: "इस दस्तावेज़ से कोई प्रयोगशाला परिणाम नहीं निकला।",
    documentsLoadFailed: "दस्तावेज़ लोड नहीं हो सके", chooseDocument: "दस्तावेज़ चुनें",
    uploadReports: "रिपोर्ट अपलोड करें", maxUpload: "अधिकतम 10 फ़ाइलें; हर फ़ाइल 8 MiB और कुल 32 MiB तक।",
    chooseAtLeastOne: "कम से कम एक फ़ाइल चुनें।", uploadFailed: "अपलोड विफल",
    processingDocuments: "दस्तावेज़ों की प्रक्रिया जारी है…", retryFailed: "दोबारा प्रक्रिया विफल",
    categoryUpdated: "दस्तावेज़ का प्रकार बदल गया।", categoryFailed: "दस्तावेज़ का प्रकार नहीं बदला जा सका",
    removeDocument: "दस्तावेज़ हटाएँ",
    removeConfirm: "क्या आप इस दस्तावेज़ को अपनी सूची से हटाना चाहते हैं? जमा मुलाकात की प्रति नहीं बदलेगी।",
    documentRemoved: "दस्तावेज़ हटा दिया गया।", removalFailed: "दस्तावेज़ नहीं हटाया जा सका",
    documentTimeline: "स्वास्थ्य समयरेखा", recordedHistory: "आपका दर्ज इतिहास",
    timelineDisclaimer: "मुलाकात की तारीख और दस्तावेज़ अपलोड की तारीख अलग दिखाई जाती हैं; अपलोड की तारीख बीमारी की घटना की तारीख नहीं है।",
    encounter: "मुलाकात", document: "दस्तावेज़", emergency: "आपातकाल", urgent: "तत्काल",
    routine: "सामान्य", priority: "प्राथमिकता", status: "स्थिति", downloadSource: "मूल दस्तावेज़ डाउनलोड करें",
    timelineFailed: "समयरेखा लोड नहीं हो सकी", documentDownloadFailed: "दस्तावेज़ डाउनलोड नहीं हो सका",
    summaryEyebrow: "मेरा सारांश", clinicalSummary: "चिकित्सकीय सारांश",
    summaryDisclaimer: "मरीज़ के बताए और दस्तावेज़ से निकले तथ्यों के स्रोत दिखाए जाते हैं; जिन बातों में मतभेद हैं, उन्हें अनसुलझा रखा जाता है।",
    submitToCreateSummary: "सारांश बनाने के लिए स्वास्थ्य इतिहास का साक्षात्कार पूरा करके जमा करें।",
    summaryRecordsFailed: "सारांश के रिकॉर्ड लोड नहीं हो सके",
    latestSummaryFailed: "नवीनतम सारांश लोड नहीं हो सका",
    loginEyebrow: "सुरक्षित मरीज़ पहुँच", signInOrRegister: "लॉग इन करें या खाता बनाएँ",
    accessHelp: "अपनी स्वास्थ्य समयरेखा, रिपोर्ट और सारांश देखें।",
    signIn: "लॉग इन", register: "खाता बनाएँ", password: "पासवर्ड", show: "दिखाएँ", hide: "छिपाएँ",
    createAccount: "खाता बनाएँ", homepage: "मुख्य पृष्ठ पर लौटें",
    consentRequired: "साक्षात्कार से पहले आवश्यक", consentError: "आगे बढ़ने से पहले डॉक्टर के लिए स्वास्थ्य जानकारी दर्ज करने की सहमति दें।",
    enterAnswer: "आगे बढ़ने से पहले उत्तर चुनें या लिखें।",
    modeReady: "शुरू करने के लिए तैयार", languageSwitch: "भाषा बदलें",
    sectionChief: "मुख्य शिकायत", sectionHpi: "वर्तमान बीमारी का इतिहास",
    sectionSoc: "लक्षणों से जुड़े प्रश्न", sectionAssociated: "साथ के लक्षण",
    sectionHistory: "स्वास्थ्य इतिहास", sectionMedication: "दवाएँ और एलर्जी",
    sectionAyush: "आयुष आकलन", uploadFileLimits: "PDF, JPG, PNG, WEBP, TIFF या TXT · अधिकतम 10 फ़ाइलें, हर फ़ाइल 8 MiB और कुल 32 MiB तक।",
    typeReportText: "अपनी रिपोर्ट का पाठ यहाँ लिखें।", someDocumentsAttention: "कुछ दस्तावेज़ों की स्थिति देखें; उन पर ध्यान देना आवश्यक है।",
    documentsProcessed: "दस्तावेज़ों की प्रक्रिया पूरी हुई।", added: "जोड़ दिया गया",
    removeDocumentConfirm: "क्या यह दस्तावेज़ हटाएँ?", No: "नहीं", Yes: "हाँ", close: "बंद करें"
  }
};

const PATIENT_COPY = {
  "Home": "होम", "About": "परिचय", "Audio": "ऑडियो", "Muted": "मौन",
  "Sign in": "लॉग इन", "Switch language": "भाषा बदलें",
  "Dashboard": "डैशबोर्ड", "Medical History": "स्वास्थ्य इतिहास", "Medical Reports": "मेडिकल रिपोर्ट",
  "Health Timeline": "स्वास्थ्य समयरेखा", "My Summary": "मेरा सारांश", "Patient workspace": "मरीज़ का कार्यक्षेत्र",
  "Open workspace menu": "कार्यस्थल मेनू खोलें", "Your health, organized.": "आपका स्वास्थ्य, व्यवस्थित।",
  "Welcome": "स्वागत है", "Prepare your information before your next consultation.": "अगली परामर्श मुलाकात से पहले अपनी जानकारी तैयार करें।",
  "Medical History": "स्वास्थ्य इतिहास", "Answer questions about your symptoms, health history, and medications.": "लक्षणों, स्वास्थ्य इतिहास और दवाओं के बारे में उत्तर दें।",
  "Upload and organize your reports.": "अपनी रिपोर्ट अपलोड करें और व्यवस्थित करें।",
  "Review an available generated draft and its source information.": "उपलब्ध मसौदे और उसके स्रोत की जानकारी देखें।",
  "Recent activity": "हाल की गतिविधि", "Account data": "खाते का डेटा", "Delete my data": "मेरा डेटा मिटाएँ",
  "The guided interview adapts to your answers and preserves your progress.": "यह साक्षात्कार आपके उत्तरों के अनुसार आगे बढ़ता है और आपकी प्रगति सुरक्षित रखता है।",
  "Choose a document": "दस्तावेज़ चुनें", "Uploaded documents": "अपलोड किए गए दस्तावेज़",
  "Original filename": "मूल फ़ाइल का नाम", "Extraction status": "पाठ निकालने की स्थिति",
  "Laboratory report": "प्रयोगशाला रिपोर्ट", "Prescription": "पर्चा", "Discharge summary": "डिस्चार्ज सारांश",
  "Other": "अन्य", "Not extracted": "निकाला नहीं गया", "Not recorded": "दर्ज नहीं",
  "No encounters or documents are available yet.": "अभी कोई मुलाकात या दस्तावेज़ उपलब्ध नहीं है।",
  "Clinical summary": "चिकित्सकीय सारांश", "Encounter": "मुलाकात", "Document": "दस्तावेज़",
  "Priority": "प्राथमिकता", "Status": "स्थिति", "Emergency": "आपातकाल", "Urgent": "तत्काल",
  "Routine": "सामान्य", "Not reported": "बताया नहीं गया", "Unclassified": "वर्गीकृत नहीं",
  "extracted": "पाठ निकाला गया", "partial": "आंशिक", "failed": "विफल", "needs_review": "समीक्षा आवश्यक",
  "Successful": "सफल", "Partial": "आंशिक", "Failed": "विफल", "Needs review": "समीक्षा आवश्यक",
  "Loading": "लोड हो रहा है", "Download original": "मूल दस्तावेज़ डाउनलोड करें",
  "Save category": "प्रकार सहेजें", "Retry extraction": "पाठ फिर से निकालें", "Remove document": "दस्तावेज़ हटाएँ",
  "No documents uploaded yet.": "कोई दस्तावेज़ अपलोड नहीं है।",
  "No structured facts extracted; review original document.": "कोई संरचित तथ्य नहीं निकला; मूल दस्तावेज़ की समीक्षा करें।",
  "dashboard": "डैशबोर्ड", "medicalHistory": "स्वास्थ्य इतिहास", "medicalReports": "मेडिकल रिपोर्ट",
  "timeline": "स्वास्थ्य समयरेखा", "mySummary": "मेरा सारांश", "signOut": "लॉग आउट",
  "uploadedDocuments": "अपलोड किए गए दस्तावेज़", "document": "दस्तावेज़", "menu": "मेनू",
  "patient": "मरीज़", "startInterview": "साक्षात्कार शुरू करें", "continueInterview": "साक्षात्कार जारी रखें",
  "saveCategory": "प्रकार सहेजें", "retryExtraction": "पाठ फिर से निकालें", "removeDocument": "दस्तावेज़ हटाएँ",
  "extractionStatus": "पाठ निकालने की स्थिति", "documentCategory": "दस्तावेज़ का प्रकार",
  "documentsLoadFailed": "दस्तावेज़ लोड नहीं हो सके", "documentDownloadFailed": "दस्तावेज़ डाउनलोड नहीं हो सका",
  "downloadSource": "मूल दस्तावेज़ डाउनलोड करें", "priority": "प्राथमिकता", "status": "स्थिति",
  "encounter": "मुलाकात", "documentTimeline": "स्वास्थ्य समयरेखा", "recordedHistory": "आपका दर्ज इतिहास",
  "summaryEyebrow": "मेरा सारांश", "clinicalSummary": "चिकित्सकीय सारांश",
  "noFindings": "इस दस्तावेज़ से कोई प्रयोगशाला परिणाम नहीं निकला।",
  "chooseDocument": "दस्तावेज़ चुनें", "noExtractedText": "कोई पाठ नहीं निकला। मूल दस्तावेज़ जाँचें या फिर से कोशिश करें।",
  "extractedText": "निकाला गया पाठ देखें", "viewDownloadOriginal": "मूल दस्तावेज़ डाउनलोड करें",
  "saveCategory": "प्रकार सहेजें", "retryFailed": "दोबारा प्रक्रिया विफल",
  "failed": "विफल", "uploaded": "अपलोड हुआ", "needs_review": "समीक्षा आवश्यक",
  "extracted": "पाठ निकाला गया", "reported": "बताया गया", "negative": "नहीं बताया गया",
  "uncertain": "अनिश्चित", "not_reported": "बताया नहीं गया", "discharge_summary": "डिस्चार्ज सारांश",
  "lab_report": "प्रयोगशाला रिपोर्ट", "prescription": "पर्चा", "other": "अन्य",
  "Laboratory report": "प्रयोगशाला रिपोर्ट", "Discharge summary": "डिस्चार्ज सारांश",
  "Optional: choose an unlocked or corrected replacement file": "वैकल्पिक: बिना पासवर्ड वाली या सुधारी गई फ़ाइल चुनें",
  "Diagnoses mentioned": "उल्लेखित निदान", "Medication mentions": "दवाओं का उल्लेख",
  "Allergy mentions": "एलर्जी का उल्लेख", "Laboratory findings": "प्रयोगशाला परिणाम",
  "Test": "जाँच", "Value": "मान", "Reference range": "संदर्भ सीमा",
  "Uncertainty": "अनिश्चितता", "Not provided": "नहीं दिया गया", "Not reported": "बताया नहीं गया",
  "Document extraction retried.": "दस्तावेज़ से पाठ निकालने की फिर कोशिश की गई।",
  "processed": "प्रक्रिया पूरी", "Each document shows its extraction status below.": "हर दस्तावेज़ की स्थिति नीचे दिखाई गई है।",
  "Download source": "मूल दस्तावेज़ डाउनलोड करें",
  "Medical reports": "मेडिकल रिपोर्ट",
  "Uploaded Documents": "अपलोड किए गए दस्तावेज़",
  "Upload Reports": "रिपोर्ट अपलोड करें",
  "Start Interview": "साक्षात्कार शुरू करें", "Continue Interview": "साक्षात्कार जारी रखें",
  "No documents uploaded yet.": "कोई दस्तावेज़ अपलोड नहीं है।",
  "Please choose at least one file.": "कम से कम एक फ़ाइल चुनें।",
  "Documents processed.": "दस्तावेज़ों की प्रक्रिया पूरी हुई।",
  "Some documents need attention. Review the per-file status.": "कुछ दस्तावेज़ों पर ध्यान देना आवश्यक है। हर फ़ाइल की स्थिति देखें।",
  "Processing failed": "प्रक्रिया विफल हुई", "Unreadable — type the contents": "पढ़ा नहीं जा सका — सामग्री लिखें",
  "Completed": "पूरा हुआ", "Download failed": "डाउनलोड विफल",
  "Remove this document?": "क्या यह दस्तावेज़ हटाएँ?",
  "Added": "जोड़ दिया गया", "No text was extracted. Verify the original or retry extraction.": "कोई पाठ नहीं निकला। मूल दस्तावेज़ जाँचें या फिर से कोशिश करें।",
  "Allergy": "एलर्जी", "No laboratory findings were extracted from this document.": "इस दस्तावेज़ से कोई प्रयोगशाला परिणाम नहीं निकला।",
  "Optional: choose an unlocked or corrected replacement file": "वैकल्पिक: बिना पासवर्ड वाली या सुधारी गई फ़ाइल चुनें",
  "Sign in or register": "लॉग इन करें या खाता बनाएँ",
  "An account keeps your timeline and documents. You can also start as a guest.": "खाते में आपकी समयरेखा और दस्तावेज़ सुरक्षित रहते हैं। आप अतिथि के रूप में भी शुरू कर सकते हैं।",
  "(for": "के लिए", "Your health, organized": "आपका स्वास्थ्य, व्यवस्थित",
  "Please sign in to upload reports.": "रिपोर्ट अपलोड करने के लिए लॉग इन करें।",
  "Please sign in or start as a guest before uploading reports.": "रिपोर्ट अपलोड करने से पहले लॉग इन करें या अतिथि के रूप में शुरू करें।",
  "Good morning": "सुप्रभात", "Records": "रिकॉर्ड", "Token": "टोकन", "Date": "तारीख",
  "ABDM": "ABDM", "Status": "स्थिति", "Priority": "प्राथमिकता",
  "About and help": "परिचय और सहायता", "How this kiosk helps": "यह कियोस्क कैसे मदद करता है",
  "Patients complete a guided history and can upload reports before seeing a clinician. The clinician receives a structured draft for review. This software does not diagnose or replace clinical judgement.": "मरीज़ चिकित्सक से मिलने से पहले निर्देशित स्वास्थ्य इतिहास पूरा कर सकते हैं और रिपोर्ट अपलोड कर सकते हैं। चिकित्सक को समीक्षा के लिए संरचित मसौदा मिलता है। यह सॉफ़्टवेयर निदान नहीं करता और चिकित्सकीय निर्णय का विकल्प नहीं है।",
  "Privacy": "गोपनीयता",
  "Before an interview starts, you are asked for explicit consent to record health information for your doctor. Guest working documents are removed after submission while source-linked encounter evidence remains available for doctor review. Data deletion is available from your account. ABDM sharing is not an operational integration in this application.": "साक्षात्कार से पहले डॉक्टर के लिए स्वास्थ्य जानकारी दर्ज करने की स्पष्ट सहमति माँगी जाती है। जमा करने के बाद अतिथि के अस्थायी दस्तावेज़ हटाए जाते हैं, जबकि स्रोत से जुड़े मुलाकात के साक्ष्य डॉक्टर की समीक्षा के लिए उपलब्ध रहते हैं। खाते से डेटा मिटाया जा सकता है। इस ऐप में ABDM साझा करने की सक्रिय सुविधा उपलब्ध नहीं है।",
  "Clinical support components": "चिकित्सकीय सहायता सुविधाएँ",
  "Adaptive medical history": "अनुकूलित स्वास्थ्य इतिहास",
  "Clinical documentation": "चिकित्सकीय दस्तावेज़ीकरण",
  "Safety and limitations": "सुरक्षा और सीमाएँ",
  "Not clinically validated. For evaluation and software testing.": "चिकित्सकीय रूप से मान्य नहीं। मूल्यांकन और सॉफ़्टवेयर परीक्षण के लिए।",
  "Ontology-constrained, stateful question selection. MediTOD (EMNLP 2024) is a relevant published benchmark candidate; the current policy is not a trained model.": "प्रश्नों का चयन स्वास्थ्य-विषय सूची और सत्र की स्थिति के अनुसार होता है। MediTOD (EMNLP 2024) प्रकाशित मूल्यांकन का एक प्रासंगिक आधार है; वर्तमान नीति प्रशिक्षित मॉडल नहीं है।",
  "Structured, source-aware summaries with a separate validation step.": "स्रोत सहित संरचित सारांश, जिनकी अलग से पुष्टि की जाती है।",
  "Red-flag rules are a provisional decision-support layer requiring clinical validation. Synthetic datasets are for software testing, not evidence of clinical performance.": "चेतावनी नियम अस्थायी निर्णय-सहायता हैं और चिकित्सकीय मान्यता आवश्यक है। कृत्रिम डेटा केवल सॉफ़्टवेयर परीक्षण के लिए है, चिकित्सकीय प्रदर्शन का प्रमाण नहीं।",
  "for": "के लिए", "Skip to content": "मुख्य सामग्री पर जाएँ",
  "Adjust text size": "अक्षर का आकार बदलें", "Audio prompts": "आवाज़ वाले निर्देश",
  "Switch theme": "थीम बदलें", "Light theme": "हल्की थीम", "Dark theme": "गहरी थीम",
  "No text was extracted. Verify the original or retry extraction.": "कोई पाठ नहीं निकला। मूल दस्तावेज़ जाँचें या फिर से कोशिश करें।",
  "Answer a few questions about your symptoms, health history, and medications.": "लक्षणों, स्वास्थ्य इतिहास और दवाओं के बारे में कुछ प्रश्नों के उत्तर दें।",
  "Upload prescriptions, laboratory reports, and other documents.": "पर्चे, प्रयोगशाला रिपोर्ट और अन्य दस्तावेज़ अपलोड करें।",
  "Review your recorded history.": "दर्ज स्वास्थ्य इतिहास देखें।",
  "Your recorded history, organized.": "आपका दर्ज स्वास्थ्य इतिहास, व्यवस्थित।",
  "Sign in or start an interview to create and review your health summary.": "स्वास्थ्य सारांश बनाने और देखने के लिए लॉग इन करें या साक्षात्कार शुरू करें।",
  "View Summary": "सारांश देखें", "Not started": "शुरू नहीं हुआ", "In progress": "जारी है",
  "YOUR HEALTH, ORGANIZED": "आपका स्वास्थ्य, व्यवस्थित", "MY HEALTH SUMMARY": "मेरा स्वास्थ्य सारांश",
  "Upload Medical Reports": "मेडिकल रिपोर्ट अपलोड करें", "Help & privacy": "सहायता और गोपनीयता",
  "Good morning": "सुप्रभात", "Medical history": "स्वास्थ्य इतिहास",
  "Answer a few questions about your health.": "अपने स्वास्थ्य के बारे में कुछ प्रश्नों के उत्तर दें।",
  "Upload and organize documents.": "दस्तावेज़ अपलोड करें और व्यवस्थित करें।",
  "Health timeline": "स्वास्थ्य समयरेखा", "View health summary": "स्वास्थ्य सारांश देखें",
  "A draft summary is available after you complete a history interview in this session.": "इस सत्र में स्वास्थ्य इतिहास पूरा करने के बाद सारांश का मसौदा उपलब्ध होगा।",
  "Records": "रिकॉर्ड", "Token": "टोकन", "Date": "तारीख", "ABDM": "ABDM",
  "About and help": "परिचय और सहायता", "How this kiosk helps": "यह कियोस्क कैसे मदद करता है",
  "Required before the interview begins": "साक्षात्कार शुरू करने से पहले आवश्यक",
  "Return to homepage": "मुख्य पृष्ठ पर लौटें",
  "Generated": "तैयार किया गया",
  "Not reported / not assessed / uncertain": "नहीं बताया गया / आकलन नहीं हुआ / अनिश्चित",
  "Conflicting information - not resolved automatically": "जानकारी में विरोध है — इसका अपने-आप समाधान नहीं किया गया",
  "Entered and extracted document dates conflict.": "दर्ज की गई और निकाली गई दस्तावेज़ की तारीखें अलग हैं।",
  "Verify:": "जाँचें:",
  "Source:": "स्रोत:",
  "Review:": "समीक्षा:",
  "document:": "दस्तावेज़:",
  "patient answer:": "मरीज़ का उत्तर:",
  "page": "पृष्ठ",
  "text": "पाठ",
  "reference": "संदर्भ",
  "value not extracted": "मान नहीं निकाला गया",
  "finding": "निष्कर्ष",
  "Red-Flag Suggestions — Generated by AI": "AI द्वारा तैयार चेतावनी सुझाव",
  "AI-generated decision-support information. Not a confirmed diagnosis. Review by a qualified healthcare professional is required.": "AI द्वारा तैयार निर्णय-सहायता जानकारी। यह पुष्ट निदान नहीं है। योग्य स्वास्थ्य-पेशेवर द्वारा समीक्षा आवश्यक है।",
  "Potential concerns identified for clinician review. These suggestions do not establish a diagnosis.": "चिकित्सक की समीक्षा के लिए संभावित चिंताएँ पहचानी गई हैं। ये सुझाव निदान स्थापित नहीं करते।",
  "Screening unavailable or incomplete": "जाँच उपलब्ध नहीं है या अधूरी है",
  "Why it triggered": "यह क्यों दिखाया गया",
  "Supporting statement(s)": "समर्थन देने वाले कथन",
  "Missing / uncertain information": "गुम / अनिश्चित जानकारी",
  "None identified by this rule": "इस नियम से कोई जानकारी नहीं मिली",
  "Next step": "अगला कदम",
  "Human review": "मानवीय समीक्षा",
  "Required": "आवश्यक",
  "Not required": "आवश्यक नहीं",
  "UNCERTAIN": "अनिश्चित"
};

const LANGUAGE_KEY = "mk_lang";
function getPatientLanguage() {
  return localStorage.getItem(LANGUAGE_KEY) === "hi" ? "hi" : "en";
}
function setPatientLanguage(language) {
  if (language !== "en" && language !== "hi") throw new TypeError("Unsupported patient interface language");
  localStorage.setItem(LANGUAGE_KEY, language);
  document.documentElement.lang = language;
}
function tr(key) {
  const language = getPatientLanguage();
  const value = language === "hi"
    ? PATIENT_COPY[key] || PATIENT_I18N.hi[key] || key
    : PATIENT_I18N.en[key] || key;
  if (language === "hi" && value === key && !PATIENT_TRANSLATIONS_CHECKED.has(key)) {
    PATIENT_TRANSLATIONS_CHECKED.add(key);
    if (location.hostname === "localhost" || location.hostname === "127.0.0.1") {
      console.warn(`Missing Hindi translation: ${key}`);
    }
  }
  return value;
}
const PATIENT_TRANSLATIONS_CHECKED = new Set();
function patientError(error) {
  const message = String(error?.message || error || "");
  if (getPatientLanguage() === "en") return message;
  const translations = [
    ["Not authenticated", "लॉग इन सत्र समाप्त हो गया है। फिर से लॉग इन करें।"],
    ["Wrong username or password", "यूज़रनेम या पासवर्ड सही नहीं है।"],
    ["Username already taken", "यह यूज़रनेम पहले से उपयोग में है।"],
    ["Consent to record health information", "डॉक्टर के लिए स्वास्थ्य जानकारी दर्ज करने की सहमति आवश्यक है।"],
    ["Choose at least one file", "कम से कम एक फ़ाइल चुनें।"],
    ["Unsupported file type", "यह फ़ाइल प्रकार समर्थित नहीं है। PDF, PNG, JPG, WEBP, TIFF या UTF-8 TXT चुनें।"],
    ["file is empty", "चुनी गई फ़ाइल खाली है।"],
    ["not a valid PDF", "फ़ाइल PDF नहीं है या पढ़ी नहीं जा सकती।"],
    ["encrypted or password-protected", "PDF पासवर्ड से सुरक्षित है। भरोसेमंद PDF ऐप से बिना पासवर्ड वाली प्रति बनाकर अपलोड करें।"],
    ["File too large", "फ़ाइल बहुत बड़ी है।"],
    ["Batch too large", "कुल अपलोड आकार सीमा से अधिक है।"],
    ["A batch may contain at most", "एक बार में अधिकतम 10 फ़ाइलें अपलोड की जा सकती हैं।"],
    ["Document not found", "दस्तावेज़ नहीं मिला।"],
    ["Transcript not found", "वाक् प्रतिलेख नहीं मिला।"],
    ["Transcript language does not match", "प्रतिलेख की भाषा साक्षात्कार की भाषा से मेल नहीं खाती।"],
    ["Speech recognition is not available", "इस ब्राउज़र में वाक् पहचान उपलब्ध नहीं है।"],
    ["Could not start microphone", "माइक्रोफ़ोन शुरू नहीं हो सका। अनुमति और डिवाइस जाँचें।"],
    ["No original file is available", "मूल फ़ाइल उपलब्ध नहीं है।"],
    ["The uploaded image is invalid", "अपलोड की गई छवि अमान्य या अपठनीय है।"],
    ["The uploaded PDF is invalid", "अपलोड की गई PDF अमान्य या अपठनीय है।"],
    ["This file is already in your document list", "यह फ़ाइल पहले से दस्तावेज़ सूची में है।"],
    ["Document processing failed", "दस्तावेज़ की प्रक्रिया पूरी नहीं हो सकी। मूल फ़ाइल की समीक्षा करें।"]
  ];
  const match = translations.find(([phrase]) => message.toLocaleLowerCase().includes(phrase.toLocaleLowerCase()));
  if (match) return match[1];
  console.error("Patient action failed", error);
  return "कार्यवाही पूरी नहीं हो सकी। आपकी सुरक्षित जानकारी नहीं बदली। फिर कोशिश करें।";
}
function languageSelector(id = "patient-language") {
  const language = getPatientLanguage();
  return `<label class="language-choice" for="${id}">
    <select id="${id}" aria-label="${PATIENT_I18N[language].interfaceLanguage}">
      <option value="en" ${language === "en" ? "selected" : ""}>${PATIENT_I18N[language].english}</option>
      <option value="hi" ${language === "hi" ? "selected" : ""}>${PATIENT_I18N[language].hindi}</option>
    </select></label>`;
}
function bindLanguageSelector(id = "patient-language", onChange = () => location.reload()) {
  const control = document.getElementById(id);
  if (control) control.addEventListener("change", () => {
    setPatientLanguage(control.value);
    onChange();
  });
}
function assertPatientTranslations() {
  const en = Object.keys(PATIENT_I18N.en).sort();
  const hi = Object.keys(PATIENT_I18N.hi).sort();
  if (JSON.stringify(en) !== JSON.stringify(hi)) {
    throw new Error("Patient translation dictionaries must have matching English and Hindi keys");
  }
  for (const [key, value] of Object.entries(PATIENT_COPY)) {
    if (!key.trim() || typeof value !== "string" || !value.trim()) {
      throw new Error(`Patient translation is missing a value for "${key}"`);
    }
  }
}
assertPatientTranslations();
window.MK_PATIENT_I18N = {
  dictionaries: PATIENT_I18N,
  copy: PATIENT_COPY,
  checkAll: assertPatientTranslations,
  hasKey: key => Object.prototype.hasOwnProperty.call(PATIENT_I18N.en, key)
    || Object.prototype.hasOwnProperty.call(PATIENT_COPY, key)
};
const API_BASE = (window.MEDIKIOSK_API_BASE != null
  ? String(window.MEDIKIOSK_API_BASE)
  : (["localhost", "127.0.0.1"].includes(location.hostname) ? "" : "https://medikos-backend.onrender.com")
).replace(/\/+$/, "");
let TOKEN = sessionStorage.getItem("mk_token") || "";
async function api(path, opt = {}) {
  const h = { ...(opt.headers || {}) };
  if (TOKEN) h.Authorization = "Bearer " + TOKEN;
  if (opt.json) { h["Content-Type"] = "application/json"; opt.body = JSON.stringify(opt.json); }
  const r = await fetch(API_BASE + "/api" + path, { method: opt.method || (opt.body ? "POST" : "GET"), headers: h, body: opt.body });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.detail || r.statusText);
  return d;
}
async function downloadDocument(path, filename) {
  const headers = TOKEN ? { Authorization: "Bearer " + TOKEN } : {};
  const response = await fetch(API_BASE + "/api" + path, { headers });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || response.statusText || "Document download failed.");
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "medical-document";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
function setToken(t) { TOKEN = t; sessionStorage.setItem("mk_token", t); }
function a11y() {
  const R = document.documentElement;
  const big = $("#big");
  const hc = $("#hc");
  if (big) big.onclick = () => R.toggleAttribute("data-big");
  if (hc) hc.onclick = () => R.toggleAttribute("data-hc");
}

function mkLogo({ compact = false, inverted = false } = {}) {
  const mark = `<span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" focusable="false">
    <rect width="32" height="32" rx="7" fill="currentColor"/>
    <path d="M5 17h5.2l2.3-6.2 3.4 12.4L18.6 17H27" fill="none" stroke="#F4F7F5" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>
  </svg></span>`;
  if (compact) return mark;
  return `<span class="brand"${inverted ? ' style="color:#fff"' : ""}>${mark}<span class="brand-copy"><span class="brand-name"${inverted ? ' style="color:#fff"' : ""}>MediKiosk</span></span></span>`;
}

function bindBusy(id, fn) {
  const btn = document.getElementById(id);
  if (!btn) return;
  btn.addEventListener("click", async e => {
    if (btn.disabled) return;
    btn.disabled = true;
    btn.classList.add("is-loading");
    try { await fn(e, btn); }
    finally {
      if (document.body.contains(btn)) {
        btn.disabled = false;
        btn.classList.remove("is-loading");
      }
    }
  });
}

const ICONS = {
  history: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 8v5l3 2"/></svg>`,
  reports: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></svg>`,
  timeline: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M4 6h16M4 12h10M4 18h13"/><circle cx="18" cy="12" r="1.4"/><circle cx="15" cy="18" r="1.4"/></svg>`,
  summary: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M6 4h12v16H6z"/><path d="M9 8h6M9 12h6M9 16h3"/></svg>`,
  privacy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>`,
  upload: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M12 16V6M8 10l4-4 4 4"/><path d="M5 18h14"/></svg>`,
  warn: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 4 3 19h18L12 4z"/><path d="M12 10v5M12 17.5v.5"/></svg>`
};

/* ── Clinical report: summary → red-flag suggestions → clinician review ──
   Block order is fixed by report.display_order; the red-flag block is ALWAYS the next sibling of the summary. */
const RF_LABEL = "Red-Flag Suggestions — Generated by AI";
const RF_NOTICE = "AI-generated decision-support information. Not a confirmed diagnosis. Review by a qualified healthcare professional is required.";
const RF_UNAVAILABLE = "Red-flag screening is unavailable or incomplete for this record. This is not a clear result; obtain clinician review.";
const RF_NONE = "No red-flag rule was triggered by the available information. This does not rule out an emergency.";

function sourceClass(ref) {
  if (!ref) return "source-system";
  if (ref.source_type === "document") return "source-document";
  if (ref.source_type === "patient") return "source-patient";
  return "source-system";
}

function reportUi(text, opt) {
  return opt.mode === "patient" ? tr(text) : text;
}

function reportSummaryHtml(rep, opt) {
  const cs = rep.clinical_summary, edit = opt.mode === "clinician";
  const refs = x => (x.source_refs || []).map(r => {
    const label = r.source_type === "document"
      ? `${reportUi("document:", opt)} ${r.filename || r.source_id}`
      : `${reportUi("patient answer:", opt)} ${r.source_id}`;
    return `<span class="source-badge ${sourceClass(r)}">${esc(label)}</span>`;
  }).join(" ");
  const findings = x => (x.findings || []).length ? `<ul class="caption evidence-list">${x.findings.map(f => {
    const source = f.source || {};
    const value = f.test_name
      ? `${f.test_name}: ${f.result ?? "value not extracted"}${f.unit ? ` ${f.unit}` : ""}${f.reference_interval ? ` · reference ${f.reference_interval}` : ""}`
      : `${f.field || reportUi("finding", opt)}: ${typeof f.value === "string" ? f.value : JSON.stringify(f.value ?? reportUi("value not extracted", opt))}`;
    const date = f.report_date || f.extracted_report_date || f.entered_document_date;
    const location = [f.source_document, date, source.page ? `${reportUi("page", opt)} ${source.page}` : null,
      source.start != null && source.end != null ? `${reportUi("text", opt)} ${source.start}-${source.end}` : null].filter(Boolean).join(" · ");
    return `<li><b>${esc(value)}</b>${f.status ? ` · ${esc(f.status)}` : ""}
      ${location ? `<br><span class="mut">${esc(location)}</span>` : ""}
      ${f.date_conflict ? `<br><span class="caption" style="color:var(--warning)">${reportUi("Entered and extracted document dates conflict.", opt)}</span>` : ""}
      ${f.uncertainty?.length ? `<br><span class="caption" style="color:var(--warning)">${reportUi("Verify:", opt)} ${esc(f.uncertainty.join("; "))}</span>` : ""}
      ${f.verification_status ? `<br><span class="mut">${esc(f.verification_status.replace(/_/g, " "))}</span>` : ""}</li>`;
  }).join("")}</ul>` : "";
  const miss = cs.missing_or_uncertain || {};
  const secs = (opt.sections || cs.sections).map((x, i) => `
    <div class="sum-sec">
      <h3>${esc(x.title)}</h3>
      ${x.text ? (edit ? `<textarea data-i="${i}" aria-label="${esc(x.title)}" style="min-height:${Math.min(200, 60 + x.text.length / 2)}px">${esc(x.text)}</textarea>`
             : `<p>${esc(x.text)}</p>`) : ""}
      ${findings(x)}
      ${(cs.sections[i] && refs(cs.sections[i])) ? `<p class="caption mut">${reportUi("Source:", opt)} ${refs(cs.sections[i])}</p>` : ""}
      ${(cs.sections[i] && (cs.sections[i].review_flags || []).length) ? `<p class="caption" style="color:var(--warning)">${reportUi("Review:", opt)} ${esc(cs.sections[i].review_flags.join(", "))}</p>` : ""}
    </div>`).join("");
  const nc = (miss.not_collected || []).map(m => `<li>${esc(m.label)}: <b>${esc(m.status)}</b></li>`).join("");
  const un = (miss.uncertain || []).map(u => `<li>${esc(u.concept)} \u2014 patient unsure: \u201C${esc(u.quote)}\u201D (${esc(u.source_label)})</li>`).join("");
  const cf = (cs.conflicts || []).map(c => `<li><b>${esc(c.concept)}</b> (${esc(c.type.replace(/_/g, " "))}) \u2014 ${esc(c.resolution || "")}</li>`).join("");
  return `<section class="rep-card" id="ai-summary" aria-labelledby="ai-summary-h" data-block="clinical_summary">
    <div class="row" style="justify-content:space-between;align-items:flex-start;flex-wrap:wrap">
      <h2 id="ai-summary-h">${esc(cs.label)}</h2>
      <span class="chip chip-urgent" data-testid="summary-status">${esc(cs.status_text)}</span>
    </div>
    <p class="caption mut">${reportUi("Generated", opt)} ${esc(cs.generated_at)} \u00B7 ${esc(cs.generator.method)}</p>
    ${secs}
    <details class="mt-sm" open><summary><b>${reportUi("Not reported / not assessed / uncertain", opt)}</b></summary>
      <ul class="caption">${nc}${un}</ul></details>
    ${cf ? `<div class="alert alert-urgent mt-sm" role="note"><div><b>${reportUi("Conflicting information - not resolved automatically", opt)}</b><ul>${cf}</ul></div></div>` : ""}
    <p class="caption mut">${esc(cs.provenance_note)}</p>
  </section>`;
}

function reportRedFlagsHtml(rep, opt) {
  const rf = rep.red_flag_suggestions, review = (rep.clinician_review || {}).finding_reviews || {};
  const edit = opt.mode === "clinician";
  const icon = u => u === "EMERGENCY" ? "Emergency" : "Urgent";
  let body;
  if (rf.screening_status !== "complete") {
    body = `<div class="rf-state rf-unavailable" role="alert">
      <div><b>${reportUi("Screening unavailable or incomplete", opt)}</b><br>${esc(rf.message || RF_UNAVAILABLE)}</div></div>`;
  } else if (!rf.items.length) {
    body = `<div class="rf-state rf-none" role="status"><div>${esc(rf.message || RF_NONE)}</div></div>`;
  } else {
    body = rf.items.map(it => `
      <article class="rf-item rf-${esc(it.urgency.toLowerCase())}" ${it.urgency === "EMERGENCY" ? 'role="alert"' : ""} data-rule="${esc(it.rule_id)}">
        <h3><span aria-hidden="true">${ICONS.warn}</span> <span class="rf-urg">${esc(it.urgency)}</span> \u2014 ${esc(it.title)}</h3>
        ${it.immediate_instruction ? `<p class="rf-now"><b>${esc(it.immediate_instruction)}</b></p>` : ""}
        <dl>
          <dt>${reportUi("Why it triggered", opt)}</dt><dd>${esc(it.reason)}</dd>
          <dt>${reportUi("Supporting statement(s)", opt)}</dt>
          <dd><ul>${it.evidence.map(e => `<li>\u201C${esc(e.quote)}\u201D <span class="caption mut">\u2014 ${esc(e.source_label)} \u00B7 <code>${esc(e.source_id)}</code>${e.temporal ? " \u00B7 " + esc(e.temporal) : ""}${e.assertion === "uncertain" ? " \u00B7 UNCERTAIN" : ""}</span>
            ${e.uncertainty_note ? `<br><span class="caption" style="color:var(--warning)">${reportUi("Review:", opt)} ${esc(e.uncertainty_note)}</span>` : ""}</li>`).join("")}</ul></dd>
          <dt>${reportUi("Missing / uncertain information", opt)}</dt><dd>${it.missing_information.length ? esc(it.missing_information.join("; ")) : reportUi("None identified by this rule", opt)}</dd>
          <dt>${reportUi("Next step", opt)}</dt><dd>${esc(it.next_step)} <span class="caption mut">(${esc(it.rule_review_note)}; ${esc(it.rule_source)})</span></dd>
          <dt>${reportUi("Human review", opt)}</dt><dd>${it.human_review_required ? reportUi("Required", opt) : reportUi("Not required", opt)}</dd>
        </dl>
        ${edit ? `<div class="review-group" role="group" aria-label="Review ${esc(it.rule_id)}">
          <label><input type="radio" name="fr-${esc(it.rule_id)}" value="confirmed" ${review[it.rule_id] === "confirmed" ? "checked" : ""}> Accept</label>
          <label><input type="radio" name="fr-${esc(it.rule_id)}" value="rejected" ${review[it.rule_id] === "rejected" ? "checked" : ""}> Reject</label>
          <label><input type="radio" name="fr-${esc(it.rule_id)}" value="needs_review" ${review[it.rule_id] === "needs_review" ? "checked" : ""}> Request clarification</label>
        </div>` : ""}
      </article>`).join("");
  }
  const notes = (rf.context_notes || []).map(n => `<li>${esc(n)}</li>`).join("");
  const miss = (rf.missing_information || []).length ? `<p class="caption">Missing information (not treated as absent): ${esc(rf.missing_information.join("; "))}</p>` : "";
  return `<section class="rep-card rf-section" id="red-flag-suggestions" aria-labelledby="rf-h" data-block="red_flag_suggestions">
    <h2 id="rf-h">${esc(reportUi(rf.label || RF_LABEL, opt))}</h2>
    <p class="rf-notice" data-testid="rf-notice"><b>${esc(reportUi(rf.notice || RF_NOTICE, opt))}</b></p>
    <p class="rf-explain">${reportUi("Potential concerns identified for clinician review. These suggestions do not establish a diagnosis.", opt)}</p>
    ${body}${miss}${notes ? `<div class="caption"><b>Context for clinician</b><ul>${notes}</ul></div>` : ""}
  </section>`;
}

function reportReviewHtml(rep, opt) {
  const cr = rep.clinician_review || {};
  const state = cr.approved ? `Approved by ${esc(cr.reviewed_by)}` : cr.status === "rejected" ? `Rejected by ${esc(cr.reviewed_by)}` : "Not yet reviewed";
  return `<section class="rep-card" id="clinician-review" aria-labelledby="cr-h" data-block="clinician_review">
    <h2 id="cr-h">Clinician review</h2>
    <p class="caption" data-testid="review-state">Status: <b>${state}</b>. Edit the summary above, confirm or reject each red-flag finding, then approve. Nothing here is an approved record until you approve it.</p>
    <div class="row mt" style="flex-wrap:wrap">
      <button class="btn btn-teal" id="cf">Approve summary</button>
      <button class="btn btn-outline" id="am">Save as amended</button>
      <button class="btn btn-outline btn-danger" id="rj">Reject</button>
      <button class="btn btn-outline" id="fhbtn">{ } Export FHIR</button>
    </div></section>`;
}

/* opt: { mode: "patient" | "clinician", sections?: edited sections }.  Returns the three blocks in display_order. */
function renderClinicalReport(rep, opt = {}) {
  const parts = { clinical_summary: reportSummaryHtml, red_flag_suggestions: reportRedFlagsHtml,
                  clinician_review: opt.mode === "clinician" ? reportReviewHtml : () => "" };
  return (rep.display_order || ["clinical_summary", "red_flag_suggestions", "clinician_review"]).map(k => (parts[k] ? parts[k](rep, opt) : "")).join("");
}
