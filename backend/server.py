from fastapi import FastAPI, APIRouter, BackgroundTasks, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import logging
import uuid
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import scanner
import report

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("server")

app = FastAPI()
api_router = APIRouter(prefix="/api")

scheduler = AsyncIOScheduler(timezone="Europe/Amsterdam")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def get_settings_full():
    doc = await db.settings.find_one({"id": "global"}, {"_id": 0})
    if not doc:
        await db.settings.insert_one(dict(scanner.DEFAULT_SETTINGS))
        return dict(scanner.DEFAULT_SETTINGS)
    
    # Zorg dat alle standaard landen aanwezig zijn (voeg nieuwe landen toe)
    default_countries = scanner.DEFAULT_COUNTRIES
    db_countries = doc.get("countries", [])
    
    # Maak een map van bestaande landen (behoud enabled status)
    country_map = {c["code"]: c for c in db_countries}
    
    # Voeg nieuwe landen toe die nog niet bestaan
    updated_countries = []
    for dc in default_countries:
        code = dc["code"]
        if code in country_map:
            # Bestaand land — behoud user settings
            updated_countries.append(country_map[code])
        else:
            # Nieuw land — voeg toe als standaard (enabled)
            updated_countries.append(dict(dc))
    
    # Controleer of er nieuwe landen zijn toegevoegd
    default_codes = set(c["code"] for c in default_countries)
    db_codes = set(c["code"] for c in db_countries)
    needs_update = False
    
    if doc.get("config_version", 1) < scanner.DEFAULT_SETTINGS["config_version"]:
        needs_update = True
    
    if db_codes != default_codes:
        needs_update = True
    
    if needs_update:
        update_data = {
            "config_version": scanner.DEFAULT_SETTINGS["config_version"],
            "countries": updated_countries,
        }
        # Update alleen deze velden, behoud de rest
        await db.settings.update_one({"id": "global"}, {"$set": update_data})
        doc = await db.settings.find_one({"id": "global"}, {"_id": 0})
    
    merged = dict(scanner.DEFAULT_SETTINGS)
    merged.update(doc or {})
    # Zorg dat de bijgewerkte landenlijst in de merged settings staat
    merged["countries"] = updated_countries
    return merged


async def get_settings():
    """Publieke settings — SMTP-wachtwoord gemaskeerd."""
    s = dict(await get_settings_full())
    s["smtp_password_set"] = bool(s.get("smtp_password"))
    s["smtp_password"] = ""
    return s


def smtp_cfg(settings):
    return {k: settings.get(k) for k in
            ("smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_from")}


# De asyncio-taak van de lopende scan, zodat /scan/cancel hem echt kan stoppen.
_current_scan_task: Optional[asyncio.Task] = None


def _scan_is_running():
    return _current_scan_task is not None and not _current_scan_task.done()


async def run_scan_job(trigger="handmatig"):
    global _current_scan_task
    # voorkom overlappende scans (dubbel scrapen veroorzaakt extra blokkades)
    if _scan_is_running() or await db.scan_runs.count_documents({"status": "bezig"}) > 0:
        logger.info("Scan overgeslagen — er loopt er al één.")
        return None
    _current_scan_task = asyncio.current_task()
    settings = await get_settings_full()
    run_id = str(uuid.uuid4())
    run_doc = {
        "id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "status": "bezig",
        "trigger": trigger,
        "is_demo": False,
        "stats": {},
        "log": [],
    }
    await db.scan_runs.insert_one(dict(run_doc))
    try:
        stats, log_lines = await scanner.perform_scan(db, settings, run_id)
    except asyncio.CancelledError:
        # cancel_scan_job heeft de run al op 'onderbroken' gezet; geen rapport/mail.
        logger.info("Scan geannuleerd.")
        return run_id
    except Exception as e:
        logger.exception("Scan mislukt")
        await db.scan_runs.update_one({"id": run_id}, {"$set": {
            "status": "mislukt", "finished_at": datetime.now(timezone.utc).isoformat(),
            "log": [f"Fout: {e}"]}})
        return run_id

    # tussentijds geannuleerd? dan geen rapport en geen mail
    current = await db.scan_runs.find_one({"id": run_id}, {"status": 1})
    if not current or current.get("status") != "bezig":
        return run_id

    # rapport genereren
    listings = await db.listings.find({"run_id": run_id}, {"_id": 0}).to_list(1000)
    subject, html = report.build_email_html(listings, stats, settings, datetime.now(timezone.utc))
    mail_status = report.send_email(subject, html, settings["recipient_email"], smtp_cfg(settings))
    report_doc = {
        "id": str(uuid.uuid4()),
        "run_id": run_id,
        "subject": subject,
        "html": html,
        "recipient": settings["recipient_email"],
        "sent": mail_status["sent"],
        "send_reason": mail_status["reason"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.email_reports.insert_one(dict(report_doc))
    await db.scan_runs.update_one({"id": run_id, "status": "bezig"}, {"$set": {
        "status": "voltooid",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "log": log_lines,
        "report_id": report_doc["id"],
        "mail_sent": mail_status["sent"],
        "mail_reason": mail_status["reason"],
    }})
    return run_id


async def reschedule():
    settings = await get_settings()
    hh, mm = (settings.get("send_time") or "08:00").split(":")
    try:
        scheduler.remove_job("daily_scan")
    except Exception:
        pass
    scheduler.add_job(run_scan_job, CronTrigger(hour=int(hh), minute=int(mm)),
                      id="daily_scan", replace_existing=True, kwargs={"trigger": "dagelijks"})
    logger.info(f"Dagelijkse scan gepland om {settings.get('send_time')} {settings.get('timezone')}.")


async def seed_demo():
    count = await db.scan_runs.count_documents({})
    if count > 0:
        return
    run_id = str(uuid.uuid4())
    listings = scanner.demo_listings(run_id)
    for l in listings:
        await db.listings.insert_one(dict(l))
    settings = await get_settings()
    stats = {"candidates": 6, "analyzed": 6, "available": 5, "excluded": 1, "errors": 0}
    subject, html = report.build_email_html(listings, stats, settings, datetime.now(timezone.utc))
    report_doc = {
        "id": str(uuid.uuid4()), "run_id": run_id, "subject": subject, "html": html,
        "recipient": settings["recipient_email"], "sent": False,
        "send_reason": "Demo — niet verzonden.", "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.email_reports.insert_one(dict(report_doc))
    await db.scan_runs.insert_one({
        "id": run_id, "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(), "status": "voltooid",
        "trigger": "demo", "is_demo": True, "stats": stats, "log": ["Demo-run met voorbeelddata."],
        "report_id": report_doc["id"], "mail_sent": False, "mail_reason": "Demo — niet verzonden.",
    })
    logger.info("Demo-run geseed.")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class SettingsUpdate(BaseModel):
    recipient_email: Optional[str] = None
    send_time: Optional[str] = None
    max_results_per_query: Optional[int] = None
    max_pages_per_run: Optional[int] = None
    include_marketplaces: Optional[bool] = None
    chip_variants: Optional[List[str]] = None
    countries: Optional[List[dict]] = None
    reference_prices: Optional[dict] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@api_router.get("/")
async def root():
    return {"message": "Mac Studio Beschikbaarheid Zoeker API"}


@api_router.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy", "service": "maczoeker-api"}


@api_router.get("/settings")
async def read_settings():
    return await get_settings()


@api_router.put("/settings")
async def update_settings(payload: SettingsUpdate):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    # leeg wachtwoord = niet wijzigen (behoud bestaande)
    if updates.get("smtp_password", None) == "":
        updates.pop("smtp_password", None)
    await db.settings.update_one({"id": "global"}, {"$set": updates}, upsert=True)
    await reschedule()
    return await get_settings()


@api_router.post("/email/test")
async def email_test():
    settings = await get_settings_full()
    rep = await db.email_reports.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    if rep and rep.get("html"):
        subject, html = f"[TEST] {rep['subject']}", rep["html"]
    else:
        subject = "[TEST] Mac Studio Beschikbaarheid Zoeker"
        html = ("<div style='font-family:Arial;padding:20px;'>"
                "<h2>Testmail</h2><p>Dit is een testbericht vanuit de Mac Studio "
                "Beschikbaarheid Zoeker. Als je dit ontvangt, werkt de e-mailverzending.</p></div>")
    status = report.send_email(subject, html, settings["recipient_email"], smtp_cfg(settings))
    return status


async def cancel_scan_job():
    """Stop de lopende scan-taak en markeer de run als 'onderbroken'."""
    running = await db.scan_runs.find_one({"status": "bezig"}, {"_id": 0})
    task_running = _scan_is_running()
    if not running and not task_running:
        return {"message": "Er loopt geen actieve scan.", "status": "geen"}
    if running:
        await db.scan_runs.update_one({"id": running["id"]}, {
            "$set": {"status": "onderbroken",
                     "finished_at": datetime.now(timezone.utc).isoformat()},
            "$push": {"log": f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} — "
                             "Scan handmatig gestopt door gebruiker."},
        })
    if task_running:
        _current_scan_task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(_current_scan_task), timeout=10)
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass
    logger.info("Scan gestopt door gebruiker.")
    return {"message": "Scan gestopt.", "status": "onderbroken"}


@api_router.post("/scan/run")
async def trigger_scan(background_tasks: BackgroundTasks):
    if _scan_is_running() or await db.scan_runs.count_documents({"status": "bezig"}) > 0:
        return {"message": "Er loopt al een scan — even geduld.", "status": "bezig"}
    background_tasks.add_task(run_scan_job, "handmatig")
    return {"message": "Scan gestart. Dit kan enkele minuten duren.", "status": "bezig"}


@api_router.post("/scan/cancel")
async def cancel_scan():
    """Stop de lopende scan."""
    return await cancel_scan_job()


@api_router.get("/scan/runs")
async def list_runs():
    runs = await db.scan_runs.find({}, {"_id": 0, "log": 0}).sort("started_at", -1).to_list(50)
    return runs


@api_router.get("/scan/current")
async def scan_current():
    """Actieve run (status=bezig) inclusief live voortgang, of meest recente run."""
    # Eerst zoeken naar een actieve scan
    active = await db.scan_runs.find_one({"status": "bezig"}, {"_id": 0})
    if active:
        return active
    # Geen actieve scan? Geef de meest recente run
    run = await db.scan_runs.find_one({}, {"_id": 0}, sort=[("started_at", -1)])
    return run or {}


@api_router.get("/scan/runs/{run_id}")
async def get_run(run_id: str):
    run = await db.scan_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(404, "Run niet gevonden")
    return run


@api_router.get("/latest")
async def latest():
    """Geef de meest recente run die klaar is (voltooid/mislukt/onderbroken), of de actieve run."""
    # Importeer de quality score functie
    from scanner import calculate_quality_score
    
    # Eerst zoeken naar de meest recente run die klaar is
    finished = await db.scan_runs.find_one(
        {"status": {"$in": ["voltooid", "mislukt", "onderbroken"]}},
        {"_id": 0}, sort=[("started_at", -1)])
    
    if finished:
        # Er is een voltooide run - check of er een nieuwere actieve run is
        active = await db.scan_runs.find_one({"status": "bezig"}, {"_id": 0})
        if active and datetime.fromisoformat(active["started_at"].replace("Z", "+00:00")) > datetime.fromisoformat(finished["started_at"].replace("Z", "+00:00")):
            # Er is een nieuwere actieve run - toon die met de resultaten van de laatste voltooide run
            listings = await db.listings.find({"run_id": finished["id"]}, {"_id": 0}).to_list(1000)
            # Sorteer eerst op kwaliteit (hogere score eerst), dan op prijs
            listings.sort(key=lambda l: (-calculate_quality_score(l), l.get("prijs_eur") is None, l.get("prijs_eur") or 1e12))
            return {"run": active, "listings": listings, "stats": finished.get("stats", {})}
        # Geen nieuwere actieve run - toon de voltooide run
        listings = await db.listings.find({"run_id": finished["id"]}, {"_id": 0}).to_list(1000)
        # Sorteer eerst op kwaliteit (hogere score eerst), dan op prijs
        listings.sort(key=lambda l: (-calculate_quality_score(l), l.get("prijs_eur") is None, l.get("prijs_eur") or 1e12))
        return {"run": finished, "listings": listings, "stats": finished.get("stats", {})}
    
    # Geen voltooide runs - check voor actieve run
    active = await db.scan_runs.find_one({"status": "bezig"}, {"_id": 0})
    if active:
        return {"run": active, "listings": [], "stats": active.get("stats", {})}
    
    # Geen runs gevonden
    return {"run": None, "listings": [], "stats": {}}


@api_router.get("/reports/latest")
async def latest_report():
    rep = await db.email_reports.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
    return rep or {}


@api_router.get("/reports/{report_id}")
async def get_report(report_id: str):
    rep = await db.email_reports.find_one({"id": report_id}, {"_id": 0})
    if not rep:
        raise HTTPException(404, "Rapport niet gevonden")
    return rep


@api_router.get("/reference-prices")
async def reference_prices():
    s = await get_settings()
    return s.get("reference_prices", scanner.REFERENCE_PRICES)


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await get_settings()
    # verweesde runs (door herstart onderbroken) netjes afsluiten
    await db.scan_runs.update_many(
        {"status": "bezig"},
        {"$set": {"status": "onderbroken",
                  "finished_at": datetime.now(timezone.utc).isoformat()}})
    await seed_demo()
    scheduler.start()
    await reschedule()


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
