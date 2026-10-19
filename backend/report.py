"""Genereert het Nederlandstalige e-mailrapport en (optioneel) verzending via SMTP."""
import os
import re
import ssl
import html as html_lib
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from collections import Counter

logger = logging.getLogger("report")

def _e(value, default=""):
    """HTML-escape voor gescrapete/LLM-waarden (voorkomt HTML-/script-injectie)."""
    return html_lib.escape(str(value if value not in (None, "") else default), quote=True)


def _safe_url(url):
    """Alleen http(s)-links toestaan; al het andere (javascript:, data:, …) wordt '#'."""
    url = (url or "").strip()
    return _e(url) if url.lower().startswith(("http://", "https://")) else "#"


BADGE_COLORS = {
    "Scherp geprijsd": "#34d399",
    "Marktconform": "#fbbf24",
    "Boven marktprijs": "#fb7185",
    "Onbekend": "#94a3b8",
}


def build_email_html(listings, stats, settings, run_date):
    """Bouwt (subject, html) voor het dagelijkse rapport — ALLE gevonden aanbiedingen
    (bevestigd beschikbaar én onduidelijk), gesorteerd op kwaliteit en prijs."""
    # Sorteer op kwaliteit (indien beschikbaar), dan op prijs
    try:
        from scanner import calculate_quality_score
        items = sorted(listings, 
                      key=lambda l: (-calculate_quality_score(l), 
                                    l.get("prijs_eur") is None, 
                                    l.get("prijs_eur") or 1e12))
    except ImportError:
        items = sorted(listings, key=lambda l: (l.get("prijs_eur") is None, 
                                                l.get("prijs_eur") or 1e12))
    
    n_bevestigd = sum(1 for l in items if (l.get("beschikbaar") or "").upper() == "JA")
    n_onduidelijk = len(items) - n_bevestigd
    n_mismatch = sum(1 for l in items if l.get("land_mismatch"))
    
    datum = run_date.strftime("%d-%m-%Y")
    subject = f"Mac Studio beschikbaarheid — {datum} — {len(items)} gevonden"
    
    landen = Counter(l["land"] for l in items)
    verzendlanden = Counter(l.get("verzend_land", l["land"]) for l in items)
    types = Counter(l.get("verkoper_type", "onbekend") for l in items)
    condities = Counter(l.get("conditie", "onbekend") for l in items)
    
    land_txt = ", ".join(f"{_e(k)}: {v}" for k, v in landen.items()) or "—"
    type_txt = ", ".join(f"{_e(k)}: {v}" for k, v in types.items()) or "—"
    cond_txt = ", ".join(f"{_e(k)}: {v}" for k, v in condities.items()) or "—"
    
    # Stats informatie
    candidates = stats.get("candidates", 0)
    analyzed = stats.get("analyzed", 0)
    blocked = stats.get("blocked", 0)
    errors = stats.get("errors", 0)
    duplicates = stats.get("duplicates_removed", 0)
    irrelevant = stats.get("irrelevant", 0)
    unverified = stats.get("price_unverified", 0)
    
    head = f"""<div style="background:#09090b;padding:24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;color:#e5e7eb;">
    <div style="max-width:960px;margin:0 auto;">
    
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #27272a;">
        <div>
            <h1 style="font-size:24px;color:#fff;margin:0 0 4px;font-weight:600;">🖥️ Mac Studio Beschikbaarheid Zoeker</h1>
            <p style="color:#94a3b8;margin:0;font-size:14px;">Dagelijks rapport — {datum}</p>
        </div>
        <div style="text-align:right;">
            <p style="color:#64748b;margin:0;font-size:12px;">Scan uitgevoerd om {run_date.strftime('%H:%M')} uur</p>
        </div>
    </div>
    
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">
        <div style="background:#18181b;border:1px solid #27272a;border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#34d399;">{len(items)}</div>
            <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;">Totaal Gevonden</div>
        </div>
        <div style="background:#18181b;border:1px solid #27272a;border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#34d399;">{n_bevestigd}</div>
            <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;">Bevestigd</div>
        </div>
        <div style="background:#18181b;border:1px solid #27272a;border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#fbbf24;">{n_onduidelijk}</div>
            <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;">Onduidelijk</div>
        </div>
        <div style="background:#18181b;border:1px solid #27272a;border-radius:10px;padding:16px;text-align:center;">
            <div style="font-size:28px;font-weight:700;color:#60a5fa;">{len(landen)}</div>
            <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;margin-top:4px;">Landen</div>
        </div>
    </div>
    
    <div style="background:#121214;border:1px solid #27272a;border-radius:10px;padding:14px;margin-bottom:20px;font-size:12px;color:#94a3b8;">
        <strong style="color:#cbd5e1;">Scan statistieken:</strong> {candidates} pagina's gescand · {analyzed} geanalyseerd · {blocked} geblokkeerd · {duplicates} dubbele verwijderd · {irrelevant} zonder Mac Studio · {unverified} prijzen niet te verifiëren · {errors} fouten
        {' · ⚠️ ' + str(n_mismatch) + ' land mismatch' if n_mismatch > 0 else ''}
    </div>"""
    
    if not items:
        body = """<div style="background:#18181b;border:1px solid #27272a;border-radius:10px;padding:32px;text-align:center;">
        <p style="font-size:18px;color:#e5e7eb;margin:0 0 8px;">Geen Mac Studio's gevonden vandaag.</p>
        <p style="color:#94a3b8;font-size:14px;margin:0;">Er zijn wel bronnen doorzocht, maar er is geen enkel aanbod aangetroffen dat als bestelbaar is geverifieerd.</p>
        </div>"""
        return subject, head + body + "</div></div>"
    
    summary = f"""<div style="background:#18181b;border:1px solid #27272a;border-radius:10px;padding:16px;margin-bottom:20px;">
    <p style="margin:0 0 8px;font-size:15px;color:#fff;"><strong>{len(items)}</strong> Mac Studio's gevonden vandaag
    — <span style="color:#34d399;">{n_bevestigd} bevestigd beschikbaar</span>, <span style="color:#fbbf24;">{n_onduidelijk} onduidelijk</span>.</p>
    <p style="margin:0 0 4px;font-size:13px;color:#94a3b8;"><strong>Per land:</strong> {land_txt}</p>
    <p style="margin:0 0 4px;font-size:13px;color:#94a3b8;"><strong>Per verkoper type:</strong> {type_txt}</p>
    <p style="margin:0;font-size:13px;color:#94a3b8;"><strong>Per conditie:</strong> {cond_txt}</p>
    </div>"""
    
    rows = ""
    for l in items:
        color = BADGE_COLORS.get(l.get("marktconformiteit"), "#94a3b8")
        prijs = f"€ {l['prijs_eur']:,.0f}".replace(",", ".") if l.get("prijs_eur") else "—"
        prijs_orig = ""
        if l.get("valuta") and l["valuta"] != "EUR" and l.get("prijs_origineel"):
            prijs_orig = f'<br><span style="color:#64748b;font-size:11px;">{_e(l["prijs_origineel"])} {_e(l["valuta"])}</span>'
        
        ja = (l.get("beschikbaar") or "").upper() == "JA"
        status_color = "#34d399" if ja else "#fbbf24"
        status_txt = "Bevestigd" if ja else "Onduidelijk"
        
        verzend_land = _e(l.get("verzend_land", l.get("land", "")))
        land_mismatch = l.get("land_mismatch", False)
        mismatch_badge = ' ⚠️ <span style="color:#fbbf24;font-size:11px;">Mismatch</span>' if land_mismatch else ''
        
        conditie_badge = ""
        conditie = l.get("conditie", "")
        if conditie == "nieuw":
            conditie_badge = '<span style="color:#34d399;font-size:10px;">NIEUW</span>'
        elif conditie == "refurbished":
            conditie_badge = '<span style="color:#60a5fa;font-size:10px;">REFURBISHED</span>'
        elif conditie == "tweedehands":
            conditie_badge = '<span style="color:#fbbf24;font-size:10px;">TWEEDEHANDS</span>'
        
        # Gebruik advertentie_url indien beschikbaar
        link_url = _safe_url(l.get("advertentie_url") or l.get("url"))
        
        rows += f"""<tr style="border-bottom:1px solid #27272a;{'background:#fbbf24;color:#1f2937;' if land_mismatch else ''}">
        <td style="padding:12px 10px;font-size:13px;color:#fff;">
            <div style="font-weight:600;">{_e(l.get('chip'), '?')} · {_e(l.get('ram'))}/{_e(l.get('opslag'))}</div>
            <div style="margin-top:2px;">{conditie_badge}</div>
        </td>
        <td style="padding:12px 10px;font-size:14px;color:#fff;text-align:right;font-weight:bold;font-family:monospace;white-space:nowrap;">
            {prijs}{prijs_orig}
        </td>
        <td style="padding:12px 10px;font-size:13px;color:#cbd5e1;">
            <div>{_e(l.get('land'))}</div>
            <div style="color:#64748b;font-size:11px;">{_e(l.get('winkelnaam'))}</div>
        </td>
        <td style="padding:12px 10px;font-size:12px;color:#cbd5e1;">
            <div>{verzend_land}{mismatch_badge}</div>
        </td>
        <td style="padding:12px 10px;font-size:12px;color:#cbd5e1;">{_e(l.get('levertijd'), '—')}</td>
        <td style="padding:12px 10px;font-size:12px;">
            <span style="color:{status_color};font-weight:bold;">{status_txt}</span>
        </td>
        <td style="padding:12px 10px;font-size:12px;">
            <span style="color:{color};font-weight:bold;">{_e(l.get('marktconformiteit'))}</span>
        </td>
        <td style="padding:12px 10px;font-size:12px;">
            <a href="{link_url}" style="color:#60a5fa;text-decoration:none;">Bekijk →</a>
        </td>
        </tr>"""
    
    table = f"""<table style="width:100%;border-collapse:collapse;background:#18181b;border:1px solid #27272a;border-radius:10px;overflow:hidden;">
    <thead><tr style="background:#121214;">
    <th style="padding:12px 10px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Model / config</th>
    <th style="padding:12px 10px;text-align:right;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Prijs</th>
    <th style="padding:12px 10px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Land / winkel</th>
    <th style="padding:12px 10px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Verzendland</th>
    <th style="padding:12px 10px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Levertijd</th>
    <th style="padding:12px 10px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Status</th>
    <th style="padding:12px 10px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Markt</th>
    <th style="padding:12px 10px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Link</th>
    </tr></thead><tbody>{rows}</tbody></table>"""
    
    footer = """<div style="margin-top:20px;padding-top:16px;border-top:1px solid #27272a;">
    <p style="color:#64748b;font-size:12px;margin:0 0 8px;">
        <strong>Legenda:</strong><br>
        <span style="color:#34d399;">Bevestigd</span> = geverifieerd bestelbaar ·
        <span style="color:#fbbf24;">Onduidelijk</span> = controleer de advertentie<br>
        ⚠️ = verzendland verschilt van zoekland (mogelijk import)
    </p>
    <p style="color:#4b5563;font-size:11px;margin:0;">
        Automatisch gegenereerd door de Mac Studio Beschikbaarheid Zoeker ·
        Alle prijzen in EUR · Data kan afwijken van werkelijke prijzen
    </p>
    </div>"""
    
    # ---- Geblokkeerde websites sectie ----
    blocked_section = ""
    blocked_urls = stats.get("blocked_urls", [])
    if blocked_urls:
        blocked_rows = ""
        for b in blocked_urls:
            blocked_rows += f"""<tr style="border-bottom:1px solid #27272a;">
            <td style="padding:10px 12px;font-size:13px;color:#cbd5e1;">
                <a href="{_safe_url(b.get('url'))}" style="color:#60a5fa;text-decoration:none;">{_e(b.get('domain'))}</a>
            </td>
            <td style="padding:10px 12px;font-size:12px;color:#94a3b8;">{_e(b.get('reason'), 'Onbekend')}</td>
            <td style="padding:10px 12px;font-size:12px;">
                <a href="{_safe_url(b.get('url'))}" style="color:#60a5fa;text-decoration:none;" target="_blank">🔗 Open →</a>
            </td>
            </tr>"""
        blocked_section = f"""<div style="margin-top:20px;padding:16px;background:#18181b;border:1px solid #27272a;border-radius:10px;">
        <h3 style="font-size:16px;color:#fb7185;margin:0 0 12px;font-weight:600;">🚫 Geblokkeerde websites ({len(blocked_urls)})</h3>
        <p style="color:#94a3b8;font-size:12px;margin:0 0 12px;">
            Deze websites konden niet automatisch worden doorzocht vanwege anti-bot beveiliging, netwerkfouten of onvoldoende content.
            Klik op de links om handmatig te zoeken.
        </p>
        <table style="width:100%;border-collapse:collapse;background:#121214;border:1px solid #27272a;border-radius:8px;overflow:hidden;">
        <thead><tr style="background:#0f0f11;">
        <th style="padding:10px 12px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Website</th>
        <th style="padding:10px 12px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Reden</th>
        <th style="padding:10px 12px;text-align:left;font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.5px;">Handmatig zoeken</th>
        </tr></thead><tbody>{blocked_rows}</tbody></table>
        </div>"""
    
    return subject, head + summary + table + footer + blocked_section + "</div></div>"


def send_email(subject, html, recipient, cfg=None):
    """Verstuurt via SMTP. cfg (dict) heeft voorrang op omgevingsvariabelen.
    Ondersteunt STARTTLS (587) en SSL (465). Geeft dict met status terug."""
    cfg = cfg or {}
    
    def pick(key, env):
        v = cfg.get(key)
        return (str(v).strip() if v not in (None, "") else os.environ.get(env, "").strip())
    
    host = pick("smtp_host", "SMTP_HOST")
    if not host:
        return {"sent": False, "reason": "SMTP niet geconfigureerd — rapport wel gegenereerd en opgeslagen."}
    port = int(pick("smtp_port", "SMTP_PORT") or "587")
    user = pick("smtp_user", "SMTP_USER")
    password = pick("smtp_password", "SMTP_PASSWORD")
    sender = pick("smtp_from", "SMTP_FROM") or user
    recipients = [a.strip() for a in re.split(r"[,;]", recipient or "") if a.strip()]
    if not recipients:
        return {"sent": False, "reason": "Geen ontvanger ingesteld."}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html, "html"))
        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=context) as server:
                if user:
                    server.login(user, password)
                server.sendmail(sender, recipients, msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                try:
                    server.starttls(context=context)
                    server.ehlo()
                except smtplib.SMTPException:
                    pass
                if user:
                    server.login(user, password)
                server.sendmail(sender, recipients, msg.as_string())
        return {"sent": True, "reason": f"Verzonden naar {', '.join(recipients)}."}
    except Exception as e:
        logger.error(f"SMTP-verzending mislukt: {e}")
        return {"sent": False, "reason": f"SMTP-fout: {e}"}
