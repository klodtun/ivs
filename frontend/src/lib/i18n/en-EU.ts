/**
 * GDPR overlay (Regulation (EU) 2016/679). Only the strings whose wording
 * differs by regulator; everything else falls back to `en`.
 */
const enEU: Record<string, string> = {
    "lang.en-EU": "English (EU)",
    "settings.tab.logs": "Audit Logs (GDPR Art. 30)",
    "settings.tab.pdpa": "GDPR (ROPA)",
    "settings.ntp.title": "NTP Time Reference (GDPR Art. 32 integrity)",
    "settings.log.title_compliance": "Audit Log (GDPR Art. 30)",
    "settings.log.compliance_badge": "GDPR Compliant",

    // Privacy notice — GDPR Art. 13/14 information notice
    "settings.pdpa_title": "Records of Processing Activities (GDPR Art. 30)",
    "settings.pdpa_desc": "EU GDPR Regulation 2016/679 compliance",

    // Retention — GDPR Storage Limitation principle (Art. 5(1)(e))
    "retention.title": "Data Retention Policy (GDPR)",
    "retention.subtitle": "Set retention per log type. Expired data is auto-deleted under the Storage Limitation principle.",
    "retention.subtitle_short": "Configure log retention per GDPR Art. 5(1)(e) — Storage Limitation",
    "retention.legal_note": "GDPR Art. 5(1)(e) Storage Limitation — personal data shall be kept no longer than necessary for the stated purpose. The controller defines retention; the supervisory authority may require extension under Art. 17(3).",
    "retention.over_recommended": "Long retention — must justify under purpose limitation",

    // Delete confirmations
    "delete.irreversible": "Irreversible. Personal data deletion under GDPR Art. 17 (Right to Erasure) is final — export the data first if you need it.",

    // Audit detail
    "audit_detail.subtitle": "Complete record per GDPR Art. 30 (Records of Processing) and Art. 32 (Security of Processing)",
    "audit_detail.legal_note": "Timestamps verified via NTP — required under GDPR Art. 32 integrity controls",

    // App log retention reference
    "retention.desc.app_logs": "Container stdout/stderr — anonymized at ingestion (Privacy by Design, Art. 25)",

    // Privacy Notice — GDPR wording
    "pn.default_title": "Information Notice (GDPR Art. 13)",
    "pn.default_detail": "This application processes personal data. Your consent is recorded under GDPR Art. 7 and may be withdrawn at any time under Art. 7(3).",
    "pn.legal_footer": "Under GDPR Art. 7(3) — consent withdrawal must be as easy as giving it. Change at any time.",
    "pn.link_policy": "Privacy Policy (GDPR Art. 13/14)",

    // Tunnel share — GDPR wording
    "tunnel.share.subject_suffix": "access link with GDPR Art. 13 information",
    "tunnel.share.body.intro_l2": "Please review the GDPR Art. 13 information notice below before using this link.",
    "tunnel.share.body.section_notice": "⚠️  Personal Data Processing Notice (GDPR Art. 13)",
    "tunnel.share.body.howto_3": "3. Your consent will be recorded per GDPR Art. 7 — lawful basis and withdrawal rights apply",
    "tunnel.share.body.section_security": "🔒  Security Warning (GDPR Art. 32)",
    "tunnel.share.body.security_3": "• Use within your organization's policy and the GDPR principles of lawfulness, fairness, and transparency",

    // GDPR Art. 17 overlays
    "gdpr.title": "Right to Erasure (GDPR Art. 17)",
    "gdpr.subtitle": "Process a data subject's erasure request under GDPR Art. 17",
    "gdpr.subtitle_short": "Execute GDPR Art. 17 erasure",
    "gdpr.legal_note": "GDPR Art. 17 grants the data subject the right to erasure ('right to be forgotten'). Recital 26 permits pseudonymisation where outright deletion conflicts with another legal obligation (records-retention). iVS replaces PII with [ERASED_GDPR] across the relevant tables and issues a signed certificate (SHA-256) per Art. 30 accountability.",
    "gdpr.modal_legal": "GDPR Art. 17(1) — the data subject may request erasure of personal data without undue delay. Records-retention obligations (e.g. financial/audit law) permit pseudonymisation per Recital 26.",

    // PII suggestions — GDPR Art. 4(1) "personal data" examples
    "pii.national_id": "National ID / Passport (Art. 9 if applicable)",
    "pii.dob": "Date of birth",
    "pii.line_id": "Online identifier (Art. 4(1))",
    "pii.photo_bio": "Photo / Biometric data (Art. 9 special category)",
    "pii.bank_account": "Financial account",
    "pii.tax_id": "Tax / national identifier",
    "pii.org_info": "Organization affiliation",
};

export default enEU;
