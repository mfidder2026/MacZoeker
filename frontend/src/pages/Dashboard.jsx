import { useEffect, useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import {
  Desktop, MagnifyingGlass, Gear, ArrowClockwise, EnvelopeSimple,
  ArrowSquareOut, ClockCounterClockwise, Globe, Tag, CurrencyEur, Warning,
  Broadcast, Terminal, CheckCircle,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogDescription,
} from "@/components/ui/dialog";
import {
  getLatest, getRuns, runScan, cancelScan, getCurrentRun, getSettings, updateSettings, getLatestReport, sendTestEmail,
} from "@/lib/api";

const MARKT = {
  "Scherp geprijsd": "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  Marktconform: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  "Boven marktprijs": "text-rose-400 bg-rose-400/10 border-rose-400/20",
  Onbekend: "text-slate-400 bg-slate-400/10 border-slate-400/20",
};

const fmtEur = (v) =>
  v == null ? "—" : "€ " + Number(v).toLocaleString("nl-NL", { maximumFractionDigits: 0 });

function StatCard({ label, value, sub, testid }) {
  return (
    <div
      data-testid={testid}
      className="border border-[#27272a] bg-[#121214] p-6 flex flex-col justify-between"
    >
      <span className="uppercase tracking-[0.15em] text-[11px] font-semibold text-slate-400">
        {label}
      </span>
      <div className="mt-4">
        <div className="font-display text-4xl font-light text-white leading-none">{value}</div>
        {sub && <div className="text-sm text-slate-400 mt-2">{sub}</div>}
      </div>
    </div>
  );
}

function Badge({ text, className }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full border text-[12px] font-medium ${className}`}>
      {text}
    </span>
  );
}

function ListingsTable({ listings }) {
  if (!listings.length) {
    return (
      <div
        data-testid="empty-state"
        className="border border-[#27272a] bg-[#121214] p-20 text-center"
      >
        <Desktop size={56} weight="thin" className="mx-auto text-slate-600" />
        <p className="mt-5 text-slate-300 font-display text-xl">
          Vandaag geen beschikbare Mac Studio's gevonden
        </p>
        <p className="text-base text-slate-500 mt-2">
          Er zijn bronnen doorzocht, maar geen aanbod is als bestelbaar geverifieerd.
        </p>
      </div>
    );
  }
  return (
    <div className="border border-[#27272a] bg-[#121214] overflow-x-auto">
      <table className="w-full text-base" data-testid="listings-table">
        <thead>
          <tr className="border-b border-[#27272a] bg-[#0f0f11]">
            {["Model / configuratie", "Prijs", "Land / winkel", "Verzendland", "Levertijd", "Type / conditie", "Beschikbaar", "Markt", ""].map((h, i) => (
              <th key={i} className={`px-5 py-4 text-[11px] uppercase tracking-[0.12em] font-semibold text-slate-400 ${i === 1 ? "text-right" : "text-left"}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {listings.map((l) => (
            <tr
              key={l.id}
              data-testid={`listing-row-${l.id}`}
              className={`border-b border-[#1c1c1f] hover:bg-[#18181b] transition-colors ${
                l.land_mismatch ? "bg-amber-400/5" : ""
              }`}
            >
              <td className="px-5 py-4">
                <div className="text-white font-medium text-base">{l.chip || "?"}</div>
                <div className="text-slate-400 text-sm mt-0.5">{l.ram} · {l.opslag}</div>
              </td>
              <td className="px-5 py-4 text-right font-mono text-white font-semibold whitespace-nowrap text-base">
                {fmtEur(l.prijs_eur)}
                {l.valuta && l.valuta !== "EUR" && (
                  <div className="text-xs text-slate-500 font-sans mt-0.5">
                    {l.prijs_origineel} {l.valuta}
                  </div>
                )}
              </td>
              <td className="px-5 py-4">
                <div className="text-slate-200 text-sm">{l.land}</div>
                <div className="text-slate-500 text-sm mt-0.5">{l.winkelnaam}</div>
              </td>
              <td className="px-5 py-4">
                <div className={`text-sm ${l.land_mismatch ? "text-amber-400 font-medium" : "text-slate-300"}`}>
                  {l.verzend_land || l.land}
                  {l.land_mismatch && (
                    <span className="ml-1.5 text-xs bg-amber-400/20 text-amber-400 px-1.5 py-0.5 rounded">
                      ⚠ Mismatch
                    </span>
                  )}
                </div>
              </td>
              <td className="px-5 py-4 text-slate-400 text-sm">{l.levertijd || "—"}</td>
              <td className="px-5 py-4">
                <div className="text-slate-300 text-sm">{l.verkoper_type}</div>
                <div className="text-slate-500 text-sm mt-0.5 capitalize">{l.conditie}</div>
              </td>
              <td className="px-5 py-4">
                <Badge
                  text={l.beschikbaar === "JA" ? "Bevestigd" : "Onduidelijk"}
                  className={l.beschikbaar === "JA"
                    ? "text-emerald-400 bg-emerald-400/10 border-emerald-400/20"
                    : "text-amber-400 bg-amber-400/10 border-amber-400/20"}
                />
              </td>
              <td className="px-5 py-4">
                <Badge text={l.marktconformiteit} className={MARKT[l.marktconformiteit] || MARKT.Onbekend} />
              </td>
              <td className="px-5 py-4">
                {l.advertentie_url || l.url ? (
                  <a
                    href={l.advertentie_url || l.url}
                    target="_blank"
                    rel="noreferrer"
                    data-testid={`listing-link-${l.id}`}
                    className="text-slate-400 hover:text-white transition-colors inline-flex items-center gap-1.5 text-sm"
                  >
                    Bekijk <ArrowSquareOut size={14} />
                  </a>
                ) : (
                  <span className="text-slate-600 text-sm">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SettingsDialog({ settings, onSaved }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(settings);
  const [testing, setTesting] = useState(false);
  useEffect(() => setForm(settings), [settings]);
  if (!form) return null;

  const toggleCountry = (code) =>
    setForm((f) => ({
      ...f,
      countries: f.countries.map((c) => (c.code === code ? { ...c, enabled: !c.enabled } : c)),
    }));

  const buildPayload = () => ({
    recipient_email: form.recipient_email,
    send_time: form.send_time,
    max_results_per_query: Number(form.max_results_per_query),
    max_pages_per_run: Number(form.max_pages_per_run),
    include_marketplaces: form.include_marketplaces,
    countries: form.countries,
    smtp_host: form.smtp_host || "",
    smtp_port: form.smtp_port || "587",
    smtp_user: form.smtp_user || "",
    smtp_password: form.smtp_password || "",
    smtp_from: form.smtp_from || "",
  });

  const save = async () => {
    try {
      await updateSettings(buildPayload());
      toast.success("Instellingen opgeslagen");
      setOpen(false);
      onSaved();
    } catch (e) {
      toast.error("Opslaan mislukt");
    }
  };

  const testSend = async () => {
    setTesting(true);
    try {
      await updateSettings(buildPayload());
      onSaved();
      const res = await sendTestEmail();
      if (res.sent) toast.success(`Testmail verstuurd — ${res.reason}`);
      else toast.error(`Niet verstuurd — ${res.reason}`);
    } catch (e) {
      toast.error("Test mislukt");
    } finally {
      setTesting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          data-testid="open-settings-btn"
          variant="outline"
          className="rounded-full border-[#27272a] bg-transparent text-slate-300 hover:bg-[#18181b] hover:text-white active:scale-95 transition-colors text-base"
        >
          <Gear size={18} className="mr-2" /> Instellingen
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-[#121214] border-[#27272a] text-slate-200 max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display font-light text-3xl text-white">Instellingen</DialogTitle>
          <DialogDescription className="text-base text-slate-400 mt-1">
            Pas de ontvanger, verzendtijd, zoekopties en landen aan.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-6 py-3">
          <div className="grid grid-cols-2 gap-5">
            <div>
              <Label className="text-sm text-slate-400">Ontvanger e-mail</Label>
              <Input
                data-testid="input-recipient"
                className="mt-2 bg-[#09090b] border-[#27272a] text-white text-base h-10"
                value={form.recipient_email || ""}
                onChange={(e) => setForm({ ...form, recipient_email: e.target.value })}
              />
            </div>
            <div>
              <Label className="text-sm text-slate-400">Verzendtijd (dagelijks)</Label>
              <Input
                data-testid="input-sendtime"
                type="time"
                className="mt-2 bg-[#09090b] border-[#27272a] text-white text-base h-10"
                value={form.send_time || "08:00"}
                onChange={(e) => setForm({ ...form, send_time: e.target.value })}
              />
            </div>
            <div>
              <Label className="text-sm text-slate-400">Resultaten per zoekopdracht</Label>
              <Input
                data-testid="input-maxresults"
                type="number"
                className="mt-2 bg-[#09090b] border-[#27272a] text-white text-base h-10"
                value={form.max_results_per_query}
                onChange={(e) => setForm({ ...form, max_results_per_query: e.target.value })}
              />
            </div>
            <div>
              <Label className="text-sm text-slate-400">Max. pagina's per run</Label>
              <Input
                data-testid="input-maxpages"
                type="number"
                className="mt-2 bg-[#09090b] border-[#27272a] text-white text-base h-10"
                value={form.max_pages_per_run}
                onChange={(e) => setForm({ ...form, max_pages_per_run: e.target.value })}
              />
            </div>
          </div>

          <div className="flex items-center justify-between border border-[#27272a] p-4">
            <div>
              <div className="text-base text-white font-medium">Particuliere marktplaatsen meenemen</div>
              <div className="text-sm text-slate-500 mt-0.5">Marktplaats, eBay, Kleinanzeigen — apart gelabeld</div>
            </div>
            <Switch
              data-testid="switch-marketplaces"
              checked={!!form.include_marketplaces}
              onCheckedChange={(v) => setForm({ ...form, include_marketplaces: v })}
            />
          </div>

          <div>
            <Label className="text-sm uppercase tracking-[0.15em] text-slate-400 font-semibold">E-mailverzending (SMTP)</Label>
            <p className="text-sm text-slate-500 mt-2 mb-3">
              Vul de gegevens van je bestaande muzabv.nl-mailbox in om het rapport écht te versturen.
              {form.smtp_password_set && (
                <span className="text-emerald-400 block mt-1">Wachtwoord is opgeslagen — laat leeg om te behouden.</span>
              )}
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 sm:col-span-1">
                <Label className="text-sm text-slate-400">SMTP-server</Label>
                <Input
                  data-testid="input-smtp-host"
                  placeholder="smtp.muzabv.nl"
                  className="mt-2 bg-[#09090b] border-[#27272a] text-white text-base h-10"
                  value={form.smtp_host || ""}
                  onChange={(e) => setForm({ ...form, smtp_host: e.target.value })}
                />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <Label className="text-sm text-slate-400">Poort</Label>
                <Input
                  data-testid="input-smtp-port"
                  placeholder="587"
                  className="mt-2 bg-[#09090b] border-[#27272a] text-white text-base h-10"
                  value={form.smtp_port || ""}
                  onChange={(e) => setForm({ ...form, smtp_port: e.target.value })}
                />
              </div>
              <div>
                <Label className="text-sm text-slate-400">Gebruikersnaam (e-mail)</Label>
                <Input
                  data-testid="input-smtp-user"
                  placeholder="jij@muzabv.nl"
                  className="mt-2 bg-[#09090b] border-[#27272a] text-white text-base h-10"
                  value={form.smtp_user || ""}
                  onChange={(e) => setForm({ ...form, smtp_user: e.target.value })}
                />
              </div>
              <div>
                <Label className="text-sm text-slate-400">Wachtwoord</Label>
                <Input
                  data-testid="input-smtp-password"
                  type="password"
                  placeholder={form.smtp_password_set ? "••••••••" : "wachtwoord"}
                  className="mt-2 bg-[#09090b] border-[#27272a] text-white text-base h-10"
                  value={form.smtp_password || ""}
                  onChange={(e) => setForm({ ...form, smtp_password: e.target.value })}
                />
              </div>
              <div className="col-span-2">
                <Label className="text-sm text-slate-400">Afzender (optioneel, standaard = gebruikersnaam)</Label>
                <Input
                  data-testid="input-smtp-from"
                  placeholder="Mac Studio Zoeker <jij@muzabv.nl>"
                  className="mt-2 bg-[#09090b] border-[#27272a] text-white text-base h-10"
                  value={form.smtp_from || ""}
                  onChange={(e) => setForm({ ...form, smtp_from: e.target.value })}
                />
              </div>
            </div>
            <Button
              data-testid="send-test-email-btn"
              onClick={testSend}
              disabled={testing || !form.smtp_host}
              variant="outline"
              className="mt-4 rounded-full border-[#27272a] bg-transparent text-slate-300 hover:bg-[#18181b] hover:text-white active:scale-95 transition-colors disabled:opacity-50 text-base"
            >
              <EnvelopeSimple size={16} className="mr-2" />
              {testing ? "Bezig met versturen…" : "Verstuur testrapport nu"}
            </Button>
          </div>

          <div>
            <Label className="text-sm uppercase tracking-[0.15em] text-slate-400 font-semibold">Landen om te doorzoeken</Label>
            <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {form.countries?.map((c) => (
                <button
                  key={c.code}
                  data-testid={`country-toggle-${c.code}`}
                  onClick={() => toggleCountry(c.code)}
                  className={`flex items-center justify-between px-4 py-2.5 border text-base transition-colors ${
                    c.enabled
                      ? "border-emerald-400/30 bg-emerald-400/10 text-white font-medium"
                      : "border-[#27272a] bg-[#09090b] text-slate-400 hover:text-white hover:bg-[#18181b]"
                  }`}
                >
                  <span>{c.name}</span>
                  <span className="text-xs font-mono text-slate-400 ml-2">{c.code}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            data-testid="save-settings-btn"
            onClick={save}
            className="rounded-full bg-slate-100 text-slate-900 hover:bg-white active:scale-95 transition-colors text-base h-10"
          >
            Opslaan
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EmailPreview({ report }) {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          data-testid="open-email-preview-btn"
          variant="outline"
          className="rounded-full border-[#27272a] bg-transparent text-slate-300 hover:bg-[#18181b] hover:text-white active:scale-95 transition-colors"
        >
          <EnvelopeSimple size={16} className="mr-1.5" /> E-mail preview
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-[#121214] border-[#27272a] text-slate-200 max-w-3xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display font-light text-2xl text-white">Dagelijks e-mailrapport</DialogTitle>
          <DialogDescription className="text-slate-500">
            Voorbeeld van het Nederlandstalige rapport dat dagelijks wordt verstuurd.
          </DialogDescription>
        </DialogHeader>
        {report?.subject ? (
          <>
            <div className="text-xs text-slate-400 border border-[#27272a] p-3 space-y-1">
              <div><span className="text-slate-500">Aan:</span> {report.recipient}</div>
              <div><span className="text-slate-500">Onderwerp:</span> {report.subject}</div>
              <div className={report.sent ? "text-emerald-400" : "text-amber-400"}>
                {report.sent ? "Verzonden" : "Niet verzonden"} — {report.send_reason}
              </div>
            </div>
            <div
              data-testid="email-preview-content"
              className="border border-[#27272a] overflow-hidden"
              dangerouslySetInnerHTML={{ __html: report.html }}
            />
          </>
        ) : (
          <p className="text-slate-500 text-sm py-8 text-center">Nog geen rapport beschikbaar.</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ScanHistory({ runs }) {
  return (
    <div className="border border-[#27272a] bg-[#121214]">
      <div className="px-5 py-4 border-b border-[#27272a] flex items-center gap-2.5">
        <ClockCounterClockwise size={18} className="text-slate-500" />
        <span className="uppercase tracking-[0.15em] text-[11px] font-semibold text-slate-400">
          Scangeschiedenis
        </span>
      </div>
      <div className="divide-y divide-[#1c1c1f] max-h-80 overflow-y-auto" data-testid="scan-history">
        {runs.length === 0 && <div className="p-5 text-base text-slate-500">Nog geen runs.</div>}
        {runs.map((r) => (
          <div key={r.id} className="px-5 py-4 flex items-center justify-between text-base">
            <div>
              <div className="text-slate-200 text-sm">
                {new Date(r.started_at).toLocaleString("nl-NL")}
                {r.is_demo && <span className="ml-2 text-xs text-amber-400 border border-amber-400/30 rounded-full px-2 py-0.5">DEMO</span>}
              </div>
              <div className="text-sm text-slate-500 mt-0.5">
                {r.trigger} · {r.status} · {r.stats?.available ?? 0} beschikbaar
                {r.mail_reason ? ` · ${r.mail_sent ? "mail verzonden" : "mail niet verzonden"}` : ""}
              </div>
            </div>
            <span className={`text-sm font-medium ${r.status === "voltooid" ? "text-emerald-400" : r.status === "bezig" ? "text-amber-400" : "text-rose-400"}`}>
              {r.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScanProgress({ run, onStopScan }) {
  if (!run) return null;
  const p = run.progress || {};
  const c = p.counters || run.stats || {};
  const total = p.total || 0;
  const current = p.current || 0;
  const pct = total ? Math.min(100, Math.round((current / total) * 100)) : (run.status === "bezig" ? 5 : 100);
  const done = run.status !== "bezig";
  const log = run.log || [];

  return (
    <div
      data-testid="scan-progress"
      className="border border-emerald-400/20 bg-[#0d1512] overflow-hidden"
    >
      <div className="px-5 py-5 border-b border-[#1c2b24] flex items-center gap-3">
        {done ? (
          <CheckCircle size={22} weight="fill" className="text-emerald-400" />
        ) : (
          <Broadcast size={22} weight="fill" className="text-emerald-400 animate-pulse" />
        )}
        <div className="flex-1">
          <div className="text-base text-white font-medium" data-testid="scan-progress-message">
            {p.message || (done ? "Scan afgerond." : "Scan wordt gestart…")}
          </div>
          <div className="text-sm text-slate-500 uppercase tracking-[0.12em] mt-1">
            {p.phase === "zoeken" ? "Fase 1 — winkels zoeken"
              : p.phase === "analyseren" ? `Fase 2 — pagina's analyseren (${current}/${total})`
              : done ? "Voltooid" : "Bezig"}
          </div>
        </div>
        {!done && (
          <button
            data-testid="stop-scan-btn"
            onClick={onStopScan}
            className="px-4 py-2 rounded-full text-sm bg-rose-500/10 text-rose-400 border border-rose-400/30 hover:bg-rose-500/20 transition-colors flex items-center gap-2"
          >
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span>
            Stop
          </button>
        )}
        <ArrowClockwise
          size={18}
          className={`text-slate-500 ${done ? "" : "animate-spin"}`}
        />
      </div>

      {/* voortgangsbalk */}
      <div className="h-1.5 bg-[#1c2b24]">
        <div
          className="h-full bg-emerald-400 transition-[width] duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* live tellers */}
      <div className="grid grid-cols-3 sm:grid-cols-6 divide-x divide-[#1c2b24] border-b border-[#1c2b24]">
        {[
          ["Kandidaten", c.candidates ?? 0],
          ["Geanalyseerd", c.analyzed ?? 0],
          ["Beschikbaar", c.available ?? 0],
          ["Uitgesloten", c.excluded ?? 0],
          ["Geblokkeerd", c.blocked ?? 0],
          ["Fouten", c.errors ?? 0],
        ].map(([lbl, val]) => (
          <div key={lbl} className="px-4 py-3 text-center">
            <div className="font-mono text-xl text-white leading-none">{val}</div>
            <div className="text-[10px] uppercase tracking-[0.12em] text-slate-500 mt-1.5">{lbl}</div>
          </div>
        ))}
      </div>

      {/* live logboek */}
      <div className="px-5 py-4">
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.15em] text-slate-500 mb-2.5">
          <Terminal size={14} /> Live logboek
        </div>
        <div
          data-testid="scan-log"
          className="font-mono text-sm leading-relaxed text-slate-400 bg-[#09090b] border border-[#1c2b24] rounded p-4 max-h-52 overflow-y-auto flex flex-col-reverse"
        >
          <div>
            {log.slice(-40).map((line, i) => (
              <div key={i} className="whitespace-pre-wrap">{line}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState({ run: null, listings: [] });
  const [runs, setRuns] = useState([]);
  const [settings, setSettings] = useState(null);
  const [report, setReport] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(null);
  const [filter, setFilter] = useState("alle");
  const [chipFilter, setChipFilter] = useState("alle");
  const [ramFilter, setRamFilter] = useState("alle");
  const pollRef = useRef(null);

  const refresh = useCallback(async () => {
    const [l, r, rep] = await Promise.all([getLatest(), getRuns(), getLatestReport()]);
    setData(l);
    setRuns(r);
    setReport(rep);
  }, []);

  useEffect(() => {
    getSettings().then(setSettings);
    refresh();
  }, [refresh]);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const onScan = async () => {
    setScanning(true);
    setProgress({ status: "bezig", progress: { message: "Scan wordt gestart…", phase: "zoeken" } });
    try {
      await runScan();
      let ticks = 0;
      let maxTicks = 9999; // Vrijwel geen harde timeout meer - polling stopt bij status change
      let initialCandidates = null;
      let lastProgressTime = Date.now();
      const PROGRESS_TIMEOUT = 30 * 60 * 1000; // 30 minuten geen progress = waarschuwing
      
      pollRef.current = setInterval(async () => {
        ticks += 1;
        try {
          const cur = await getCurrentRun();
          
          // ALTIJD setProgress als er data is, ook als status "bezig"
          if (cur && cur.id) {
            setProgress(cur);
            lastProgressTime = Date.now();
            
            // Bereken dynamische timeout op basis van aantal pagina's
            const candidates = cur.progress?.counters?.candidates || cur.stats?.candidates || 0;
            if (candidates > 0 && initialCandidates === null) {
              initialCandidates = candidates;
              // 30 seconden per pagina + 30 minuten buffer = ruime tijd
              maxTicks = Math.ceil(candidates * 12) + 720;
            }
            
            // Check of scan klaar is
            if (cur.status && cur.status !== "bezig") {
              clearInterval(pollRef.current);
              // Eerst de data verversen VOOR de UI update
              await refresh();
              // Dan de progress en scanning state updaten
              setProgress(cur);
              setScanning(false);
              if (cur.status === "voltooid") {
                toast.success(`Scan voltooid — ${cur.stats?.available ?? 0} beschikbaar gevonden.`);
              } else if (cur.status === "mislukt") {
                toast.error("Scan mislukt. Controleer de logs voor meer informatie.");
              } else if (cur.status === "onderbroken") {
                toast.warning("Scan is onderbroken. Controleer de backend logs.");
              }
            }
          }
          
          // Check of we te lang geen progress hebben gezien
          if (Date.now() - lastProgressTime > PROGRESS_TIMEOUT && ticks > 120) {
            toast.warning("Geen progress gezien de laatste 30 minuten. Backend werkt mogelijk nog.");
          }
          
        } catch (e) {
          /* blijf pollen - progress display blijft staan */
        }
      }, 2500);
    } catch (e) {
      setScanning(false);
      toast.error("Scan starten mislukt.");
    }
  };

  const onStopScan = async () => {
    try {
      await cancelScan();
      setScanning(false);
      clearInterval(pollRef.current);
      await refresh();
      toast.info("Scan gestopt.");
    } catch (e) {
      toast.error("Stoppen van scan mislukt.");
    }
  };

  const listings = Array.isArray(data.listings) ? data.listings : [];
  
  // Extraheer beschikbare chip-types en RAM-waarden uit de listings
  const chipSet = new Set(listings.map((l) => {
    const chip = l.chip || "";
    if (!chip) return "onbekend";
    if (chip.includes("M1")) return "M1";
    if (chip.includes("M2")) return "M2";
    if (chip.includes("M3")) return "M3";
    if (chip.includes("M4")) return "M4";
    if (chip.includes("M5")) return "M5";
    return "onbekend";
  }));
  const chipOptions = ["alle", ...Array.from(chipSet).filter(Boolean)];
  
  const ramSet = new Set(listings.map((l) => {
    const ram = l.ram || "";
    if (!ram) return "onbekend";
    const match = ram.match(/(\d+)/);
    return match ? match[1] : "onbekend";
  }));
  const ramOptions = ["alle", ...Array.from(ramSet).filter(Boolean).sort((a, b) => Number(a) - Number(b))];
  
  const filtered = listings.filter((l) => {
    // Condities filter
    if (filter === "nieuw") return l.conditie === "nieuw";
    if (filter === "refurbished") return l.conditie === "refurbished";
    if (filter === "tweedehands") return l.conditie === "tweedehands";
    
    // Chip filter
    if (chipFilter !== "alle") {
      const chip = l.chip || "";
      if (chipFilter === "onbekend") {
        if (chip && !chip.includes("M1") && !chip.includes("M2") && !chip.includes("M3") && !chip.includes("M4") && !chip.includes("M5")) return false;
      } else {
        if (!chip.includes(chipFilter)) return false;
      }
    }
    
    // RAM filter
    if (ramFilter !== "alle") {
      const ram = l.ram || "";
      const match = ram.match(/(\d+)/);
      if (!match || match[1] !== ramFilter) return false;
    }
    
    return true;
  });

  const beschikbaar = listings.filter((l) => l.beschikbaar === "JA");
  const landen = new Set(beschikbaar.map((l) => l.land));
  const prijzen = beschikbaar.map((l) => l.prijs_eur).filter((p) => p != null);
  const gemiddeld = prijzen.length ? Math.round(prijzen.reduce((a, b) => a + b, 0) / prijzen.length) : null;
  const scherpste = beschikbaar
    .filter((l) => l.marktconformiteit === "Scherp geprijsd")
    .sort((a, b) => (a.prijs_eur || 1e12) - (b.prijs_eur || 1e12))[0];

  return (
    <div className="min-h-screen bg-[#09090b] text-slate-200">
      {/* Header */}
      <header className="sticky top-0 z-30 backdrop-blur-xl bg-[#09090b]/80 border-b border-[#27272a]">
        <div className="max-w-screen-2xl mx-auto px-4 md:px-8 py-5 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 border border-[#27272a] bg-[#18181b] flex items-center justify-center">
              <Desktop size={22} weight="fill" className="text-slate-200" />
            </div>
            <div>
              <h1 className="font-display text-xl font-medium text-white leading-none tracking-tight">
                Mac Studio Zoeker
              </h1>
              <span className="text-sm text-slate-500 mt-0.5 block">Beschikbaarheid in de EU · UK · CH · US</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <EmailPreview report={report} />
            {settings && <SettingsDialog settings={settings} onSaved={() => getSettings().then(setSettings)} />}
            <Button
              data-testid="run-scan-btn"
              onClick={onScan}
              disabled={scanning}
              className="rounded-full bg-slate-100 text-slate-900 hover:bg-white active:scale-95 transition-colors disabled:opacity-60 text-base h-10"
            >
              {scanning ? (
                <ArrowClockwise size={18} className="mr-2 animate-spin" />
              ) : (
                <MagnifyingGlass size={18} className="mr-2" />
              )}
              {scanning ? "Bezig met scannen…" : "Scan nu"}
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-screen-2xl mx-auto px-4 md:px-8 py-8 space-y-7">
        {scanning && <ScanProgress run={progress} onStopScan={onStopScan} />}

        {data.run?.is_demo && (
          <div
            data-testid="demo-banner"
            className="flex items-center gap-2.5 border border-amber-400/30 bg-amber-400/10 text-amber-300 px-5 py-3 text-base"
          >
            <Warning size={18} weight="fill" />
            Dit is een <strong>demo-run met voorbeelddata</strong>. Klik op "Scan nu" voor een echte live scan.
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
          <StatCard testid="stat-found" label="Beschikbaar gevonden" value={beschikbaar.length}
            sub={data.run ? `Laatste run: ${new Date(data.run.started_at).toLocaleString("nl-NL")}` : "—"} />
          <StatCard testid="stat-countries" label="Landen" value={landen.size} sub="met aanbod" />
          <StatCard testid="stat-avg" label="Gemiddelde prijs" value={fmtEur(gemiddeld)} sub="van beschikbare" />
          <StatCard testid="stat-best" label="Scherpste deal"
            value={scherpste ? fmtEur(scherpste.prijs_eur) : "—"}
            sub={scherpste ? `${scherpste.chip} · ${scherpste.land}` : "geen"} />
        </div>

        {/* Filters */}
        <div className="space-y-4">
          {/* Condities */}
          <div className="flex items-center gap-2.5 flex-wrap">
            {[
              ["alle", "Alle"],
              ["nieuw", "Nieuw"],
              ["refurbished", "Refurbished"],
              ["tweedehands", "Tweedehands"],
            ].map(([key, lbl]) => (
              <button
                key={key}
                data-testid={`filter-${key}`}
                onClick={() => setFilter(key)}
                className={`px-5 py-2 rounded-full text-base border transition-colors ${
                  filter === key
                    ? "bg-slate-100 text-slate-900 border-slate-100 font-medium"
                    : "bg-transparent border-[#27272a] text-slate-400 hover:text-white hover:bg-[#18181b]"
                }`}
              >
                {lbl}
              </button>
            ))}
          </div>

          {/* Chip type & RAM filters */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2.5">
              <span className="text-sm text-slate-500 font-medium">Chip:</span>
              <div className="flex items-center gap-2 flex-wrap">
                {chipOptions.map((opt) => (
                  <button
                    key={opt}
                    data-testid={`chip-filter-${opt}`}
                    onClick={() => setChipFilter(opt)}
                    className={`px-4 py-1.5 rounded-full text-sm border transition-colors ${
                      chipFilter === opt
                        ? "bg-blue-500 text-white border-blue-500 font-medium"
                        : "bg-transparent border-[#27272a] text-slate-400 hover:text-white hover:bg-[#18181b]"
                    }`}
                  >
                    {opt === "alle" ? "Alle chips" : opt}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="text-sm text-slate-500 font-medium">RAM:</span>
              <div className="flex items-center gap-2 flex-wrap">
                {ramOptions.map((opt) => (
                  <button
                    key={opt}
                    data-testid={`ram-filter-${opt}`}
                    onClick={() => setRamFilter(opt)}
                    className={`px-4 py-1.5 rounded-full text-sm border transition-colors ${
                      ramFilter === opt
                        ? "bg-blue-500 text-white border-blue-500 font-medium"
                        : "bg-transparent border-[#27272a] text-slate-400 hover:text-white hover:bg-[#18181b]"
                    }`}
                  >
                    {opt === "alle" ? "Alle RAM" : `${opt}GB`}
                  </button>
                ))}
              </div>
            </div>
            {(chipFilter !== "alle" || ramFilter !== "alle") && (
              <button
                data-testid="clear-advanced-filters"
                onClick={() => { setChipFilter("alle"); setRamFilter("alle"); }}
                className="px-4 py-1.5 rounded-full text-sm border border-rose-400/30 text-rose-400 hover:bg-rose-400/10 transition-colors"
              >
                ✕ Reset
              </button>
            )}
            <span className="ml-auto text-sm text-slate-500">
              {filtered.length} van {listings.length} getoond
            </span>
          </div>
        </div>

        <ListingsTable listings={filtered} />

        <ScanHistory runs={runs} />
      </main>
    </div>
  );
}
