/**
 * APPI overlay (個人情報の保護に関する法律). Core nav and compliance strings
 * only; everything else falls back to `en`.
 */
const ja: Record<string, string> = {
    "lang.ja": "日本語",

    // Sidebar
    "nav.dashboard": "ダッシュボード",
    "nav.apps": "アプリ",
    "nav.tunnels": "トンネル",
    "nav.vault": "APIキー保管庫",
    "nav.resources": "システムリソース",
    "nav.settings": "設定",
    "nav.signout": "ログアウト",

    // Login
    "login.title": "Internal Vibe Server",
    "login.username": "ユーザー名",
    "login.password": "パスワード",
    "login.submit": "ログイン",

    // Dashboard
    "dash.title": "ダッシュボード",
    "dash.refresh": "更新",
    "dash.last_updated": "最終更新",

    // Audit logs — APPI Art. 26 (records of processing) equivalent
    "settings.tab.logs": "監査ログ (APPI)",
    "settings.tab.pdpa": "APPI 取扱記録",
    "settings.ntp.title": "NTP時刻参照 (APPI 安全管理措置)",
    "settings.log.title_compliance": "監査ログ — 個人情報保護法対応",
    "settings.log.compliance_badge": "APPI準拠",

    // PDPA tab is shown but worded for APPI
    "settings.pdpa_title": "個人情報取扱記録 (APPI)",
    "settings.pdpa_desc": "個人情報の保護に関する法律 (2003年制定, 2022年改正) 対応",

    // Retention — APPI doesn't specify a minimum, but PIPC guidance
    // recommends keeping security logs for an appropriate period.
    "retention.title": "データ保存ポリシー (APPI)",
    "retention.subtitle": "各ログ種別の保存期間を設定。期限切れデータは自動削除されます",
    "retention.subtitle_short": "個人情報保護法 (APPI) に基づきログ保存期間を設定",
    "retention.legal_note": "個人情報保護法 第19条 (適正な取得) 及び 第23条 (安全管理措置)。委員会の指示によりさらに長期保存を求められる場合があります。",
    "retention.days": "日",
    "retention.default": "デフォルト",
    "retention.save": "保存",
    "retention.cancel": "キャンセル",

    // Delete confirmations
    "delete.irreversible": "取り消せません。APPI 第30条 (利用停止・消去等) に基づく個人情報の削除は最終的なものです。必要に応じて事前にエクスポートしてください。",

    // Audit detail
    "audit_detail.title": "イベント詳細",
    "audit_detail.subtitle": "個人情報保護法に基づく完全な記録",
    "audit_detail.user": "ユーザー",
    "audit_detail.resource": "リソース",
    "audit_detail.details": "詳細",
    "audit_detail.close": "閉じる",
    "audit_detail.legal_note": "NTPによりタイムスタンプ検証済み — APPI 安全管理措置の要件",

    // App log retention reference
    "retention.desc.app_logs": "コンテナ stdout/stderr — 取得時に匿名化 (Privacy by Design)",

    // Roles
    "role.admin": "管理者",
    "role.developer": "開発者",
    "role.viewer": "閲覧者",

    // Pagination
    "pagination.showing": "表示中",
    "pagination.of": "/",
    "pagination.per_page": "ページごと",

    // Privacy Notice — APPI wording
    "pn.default_title": "個人情報の取扱いに関する通知 (APPI)",
    "pn.default_detail": "本アプリケーションは個人情報を取扱います。APPI第18条 (取得時の利用目的通知) に基づきご確認ください。",
    "pn.review_badge": "同意状況の確認・変更",
    "pn.current_status": "現在の状況",
    "pn.status_accepted": "✓ 同意済み",
    "pn.status_declined": "✗ 拒否",
    "pn.recorded_at": "記録日時",
    "pn.link_policy": "個人情報保護方針",
    "pn.link_full_notice": "通知全文",
    "pn.accept_current": "✓ 同意済み (現在の選択)",
    "pn.switch_to_accept": "同意に変更",
    "pn.decline_current": "✗ 拒否 (現在の選択)",
    "pn.switch_to_decline": "拒否に変更",
    "pn.close": "閉じる",
    "pn.saving": "保存中…",
    "pn.accept_and_enter": "同意して利用する",
    "pn.decline": "拒否する",
    "pn.legal_footer": "個人情報保護法に基づき、同意はいつでも変更可能です",

    // Tunnel share — APPI wording
    "tunnel.share.subject_suffix": "APPI 通知付きアクセスリンク",
    "tunnel.share.body.greeting": "ご担当者様",
    "tunnel.share.body.intro_l1": 'アプリケーション "{app}" の一時アクセスリンクをご案内いたします。',
    "tunnel.share.body.intro_l2": "ご利用の前に、下記の個人情報取扱通知 (APPI) をご確認ください。",
    "tunnel.share.body.section_notice": "⚠️  個人情報の取扱いに関する通知 (APPI)",
    "tunnel.share.body.no_notice": "(本アプリは個人情報取扱通知が未設定です — 外部公開前に管理者による設定を推奨します)",
    "tunnel.share.body.section_link": "🔗  アクセスリンク (Tunnel)",
    "tunnel.share.body.expires_at": "リンク有効期限",
    "tunnel.share.body.section_howto": "📖  ご利用方法",
    "tunnel.share.body.howto_1": "1. 上記リンクをクリックしてアプリを開く",
    "tunnel.share.body.howto_2": "2. 個人情報取扱通知が表示された場合は、内容をご確認のうえ同意可否をご判断ください",
    "tunnel.share.body.howto_3": "3. 同意・拒否の選択は個人情報保護法に基づき記録されます",
    "tunnel.share.body.howto_4": "4. 同意状況はいつでもこのリンクから変更できます",
    "tunnel.share.body.section_security": "🔒  セキュリティ上の注意 (APPI 安全管理措置)",
    "tunnel.share.body.security_1": "• 本リンクは外部ネットワークから内部システムへのアクセスを許可するものです",
    "tunnel.share.body.security_2": "• 不適切な利用により情報漏洩のリスクがあります",
    "tunnel.share.body.security_3": "• 貴組織のセキュリティポリシーに従ってご利用ください",
    "tunnel.share.body.security_4": "• 異常を検知した場合は速やかに管理者へご連絡ください",
    "tunnel.share.body.section_note": "💬  送信者からの追記",
    "tunnel.share.body.signoff": "iVS — Internal Vibe Server より送信",

    // APPI Art. 30 overlays
    "gdpr.title": "利用停止・消去 (APPI 第30条)",
    "gdpr.subtitle": "本人からの請求に基づき個人情報を消去・匿名化します",
    "gdpr.subtitle_short": "APPI 第30条に基づく利用停止・消去",
    "gdpr.legal_note": "個人情報保護法第30条に基づく利用停止・消去請求への対応。安全管理措置 (第23条) のため、log の row 自体は削除せず PII 部分のみを [ERASED_GDPR] に置換します。SHA-256 署名付き証明書を発行します。",
    "gdpr.modal_legal": "個人情報保護法 第30条 — 本人は、保有個人データの利用停止・消去等を請求できます。安全管理措置の観点から、ログの監査証跡は保持されます。",
    "gdpr.modal_title": "個人情報消去の確認",
    "gdpr.modal_confirm": "消去を実行",

    // PII suggestion checklist — APPI Art. 2 "個人情報" examples
    "pii.full_name": "氏名",
    "pii.email": "メールアドレス",
    "pii.phone": "電話番号",
    "pii.address": "住所",
    "pii.national_id": "マイナンバー / パスポート",
    "pii.dob": "生年月日 / 年齢",
    "pii.line_id": "SNS ID (LINE等)",
    "pii.photo_bio": "顔写真 / 生体情報",
    "pii.bank_account": "金融口座情報",
    "pii.tax_id": "納税者番号",
    "pii.org_info": "所属組織情報",

    // Misc inline strings
    "user_delete.reassigned_suffix": "アプリの所有権を移譲しました:",
    "settings.export_success": "エクスポート完了",
    "settings.activities_count": "件",
    "settings.pn_saved": "通知を保存しました",
    "settings.pdpa.found": "検出",
    "settings.pdpa.not_found": "未検出",
    "settings.pdpa.add_all_detected": "検出されたすべてを追加",
    "settings.pdpa.masking_patterns_label": "マスキングパターン",
    "settings.pdpa.masking_line": "'{pattern}' を {file} で検出 ({line}行目)",
    "settings.pdpa.scan_details_label": "スキャン結果詳細",
    "settings.pdpa.items": "件",
    "settings.pdpa.col_file": "ファイル",
    "settings.pdpa.col_line": "行",
    "settings.pdpa.col_field": "フィールド",
    "settings.pdpa.col_category": "カテゴリ",
    "settings.pn_detail_placeholder": "本アプリケーションは、サービス提供の目的のために個人情報を収集・利用・開示します...",
    "settings.pn_preview_placeholder": "詳細はここに表示されます...",
    "deploy.auto_sanitize_note": "Auto-Sanitize により不要ファイルが自動削除されます",
    "deploy.close": "閉じる",
    "datepicker.clear": "クリア",
    "datepicker.today": "今日",
};

export default ja;
