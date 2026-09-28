import streamlit as st
import requests
import base64
import hashlib
import json
import uuid
from datetime import datetime, timedelta
from io import BytesIO

try:
    from PIL import Image
    PIL_VERFUEGBAR = True
except Exception:
    PIL_VERFUEGBAR = False

try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_VERFUEGBAR = True
except Exception:
    CANVAS_VERFUEGBAR = False

st.set_page_config(page_title="Aufmaß-Erfassung", layout="centered")

APP_VERSION = "1.7.0"

# ---------------------------------------------------------------------------
# Konfiguration ueber Streamlit Secrets (in Streamlit Community Cloud unter
# "Settings -> Secrets" einzutragen, siehe Anleitung im Chat):
#
# AUFMASS_PIN = "1234"
# GITHUB_TOKEN = "ghp_xxx..."
# GITHUB_REPO = "dein-github-name/aufmass-daten"
# ---------------------------------------------------------------------------
def hole_secret(name, standard=None):
    try:
        return st.secrets[name]
    except Exception:
        return standard

AUFMASS_PIN = hole_secret("AUFMASS_PIN", "0000")
GITHUB_TOKEN = hole_secret("GITHUB_TOKEN", "")
GITHUB_REPO = hole_secret("GITHUB_REPO", "")
GITHUB_BRANCH = hole_secret("GITHUB_BRANCH", "main")

MAX_BILDBREITE = 1600
JPEG_QUALITAET = 80


def github_datei_anlegen(pfad_im_repo, roh_bytes, commit_nachricht):
    """Legt eine neue Datei im konfigurierten GitHub-Repo an (Contents API)."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return False, "GitHub ist nicht konfiguriert (GITHUB_TOKEN/GITHUB_REPO fehlen in den Secrets)."
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{pfad_im_repo}"
    inhalt_b64 = base64.b64encode(roh_bytes).decode("utf-8")
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "message": commit_nachricht,
        "content": inhalt_b64,
        "branch": GITHUB_BRANCH
    }
    try:
        antwort = requests.put(url, headers=headers, json=payload, timeout=30)
        if antwort.status_code in (200, 201):
            return True, "OK"
        return False, f"GitHub-Fehler ({antwort.status_code}): {antwort.text[:300]}"
    except Exception as e:
        return False, f"Verbindungsfehler: {e}"


def github_liste(pfad_im_repo):
    """Listet den Inhalt eines Ordners im konfigurierten GitHub-Repo (z. B. offene Termine)."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return [], "GitHub ist nicht konfiguriert."
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{pfad_im_repo}?ref={GITHUB_BRANCH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    try:
        antwort = requests.get(url, headers=headers, timeout=20)
        if antwort.status_code == 200:
            return antwort.json(), None
        if antwort.status_code == 404:
            return [], None
        return [], f"GitHub-Fehler ({antwort.status_code})"
    except Exception as e:
        return [], f"Verbindungsfehler: {e}"


def github_datei_lesen(pfad_im_repo):
    """Laedt den Rohinhalt einer einzelnen Datei aus dem konfigurierten GitHub-Repo."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return None, "GitHub ist nicht konfiguriert."
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{pfad_im_repo}?ref={GITHUB_BRANCH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.raw"}
    try:
        antwort = requests.get(url, headers=headers, timeout=20)
        if antwort.status_code == 200:
            return antwort.content, None
        return None, f"GitHub-Fehler ({antwort.status_code})"
    except Exception as e:
        return None, f"Verbindungsfehler: {e}"


@st.cache_data(ttl=300)
def oeffentliches_firmenprofil_laden():
    """Holt Impressum-/Datenschutzangaben, die die Gewerbe-Zentrale unter
    'Firmenprofil' -> 'Impressum & Datenschutz' -> 'An mobile Erfassung uebertragen'
    bereitstellt. Enthaelt bewusst keine Zugangsdaten (SMTP/Telegram)."""
    roh_bytes, fehler = github_datei_lesen("oeffentlich/firmenprofil_oeffentlich.json")
    if fehler or not roh_bytes:
        return None
    try:
        return json.loads(roh_bytes.decode("utf-8"))
    except Exception:
        return None


def zeige_impressum_footer():
    """Zeigt Impressum & Datenschutzhinweis an - Pflicht fuer diese oeffentlich
    erreichbare Seite (Paragraph 5 Digitale-Dienste-Gesetz / DSGVO)."""
    profil_oeff = oeffentliches_firmenprofil_laden()
    with st.expander("Impressum & Datenschutz"):
        if not profil_oeff or not profil_oeff.get("Firmenname"):
            st.caption("Noch nicht hinterlegt. Der Betreiber kann dies in der Gewerbe-Zentrale unter 'Firmenprofil' -> 'Impressum & Datenschutz' einrichten und uebertragen.")
            return
        zeilen = [profil_oeff.get("Firmenname", "")]
        if profil_oeff.get("Rechtsform"):
            zeilen.append(f"Rechtsform: {profil_oeff['Rechtsform']}")
        if profil_oeff.get("Ansprechpartner"):
            zeilen.append(f"Vertretungsberechtigt: {profil_oeff['Ansprechpartner']}")
        if profil_oeff.get("Strasse"):
            zeilen.append(profil_oeff["Strasse"])
        if profil_oeff.get("PLZ_Ort"):
            zeilen.append(profil_oeff["PLZ_Ort"])
        if profil_oeff.get("Telefon"):
            zeilen.append(f"Telefon: {profil_oeff['Telefon']}")
        if profil_oeff.get("Email"):
            zeilen.append(f"E-Mail: {profil_oeff['Email']}")
        if profil_oeff.get("USt_ID"):
            zeilen.append(f"Umsatzsteuer-ID: {profil_oeff['USt_ID']}")
        if profil_oeff.get("Handelsregister"):
            zeilen.append(f"Handelsregister: {profil_oeff['Handelsregister']}")
        if profil_oeff.get("Handwerkskammer"):
            zeilen.append(f"Handwerkskammer/Berufsbezeichnung: {profil_oeff['Handwerkskammer']}")
        st.write("  \n".join(zeilen))
        st.caption(
            f"{profil_oeff.get('Firmenname', 'Der Betreiber')} verarbeitet die hier eingegebenen Daten "
            "(z. B. Name, Adresse, Fotos, Unterschrift) ausschliesslich zur Abwicklung des jeweiligen "
            "Auftrags und gibt sie nicht an Dritte weiter, soweit dies nicht zur Vertragserfuellung "
            "erforderlich ist."
        )


def zeige_angebot_annahme(angebotsnummer):
    """Oeffentliche Seite (kein PIN-Login noetig), ueber die ein Kunde ein per Link
    geteiltes Angebot ansehen und online annehmen kann. Wird ueber den URL-Parameter
    ?modus=angebot&nr=<Angebotsnummer> aufgerufen (Link kommt aus der Gewerbe-Zentrale,
    Report -> Angebote -> 'Online-Annahme')."""
    st.title("Ihr Angebot")
    daten_bytes, fehler_daten = github_datei_lesen(f"angebote_annahme/{angebotsnummer}/daten.json")
    if fehler_daten or not daten_bytes:
        st.error("Dieses Angebot wurde nicht gefunden oder ist nicht mehr verfuegbar. Bitte wenden Sie sich an den Absender des Links.")
        zeige_impressum_footer()
        st.stop()

    try:
        daten = json.loads(daten_bytes.decode("utf-8"))
    except Exception:
        st.error("Die Angebotsdaten konnten nicht gelesen werden.")
        zeige_impressum_footer()
        st.stop()

    st.write(f"**{daten.get('Firmenname', '')}**")
    st.write(f"Angebot **{angebotsnummer}** fuer {daten.get('Kunde', '')}")
    st.metric("Betrag", f"{float(daten.get('Betrag', 0)):.2f} EUR")
    if daten.get("Frist"):
        st.caption(f"Gueltig bis: {daten['Frist']}")

    pdf_bytes, _ = github_datei_lesen(f"angebote_annahme/{angebotsnummer}/angebot.pdf")
    if pdf_bytes:
        st.download_button("Angebot als PDF herunterladen", pdf_bytes, file_name=f"Angebot_{angebotsnummer}.pdf", mime="application/pdf")

    annahme_bytes, _ = github_datei_lesen(f"angebote_annahme/{angebotsnummer}/annahme.json")
    if annahme_bytes:
        try:
            annahme_daten = json.loads(annahme_bytes.decode("utf-8"))
            st.success(f"Dieses Angebot wurde bereits am {annahme_daten.get('Angenommen_Am', '')} online angenommen. Sie werden in Kuerze kontaktiert.")
        except Exception:
            st.success("Dieses Angebot wurde bereits online angenommen.")
        zeige_impressum_footer()
        st.stop()

    st.divider()
    widerruf_bestaetigt = True
    if daten.get("Verbraucher") and daten.get("Widerruf_Text"):
        with st.expander("Widerrufsbelehrung (bitte lesen)", expanded=True):
            st.text(daten["Widerruf_Text"])
        widerruf_bestaetigt = st.checkbox("Ich habe die Widerrufsbelehrung gelesen und moechte das Angebot annehmen.")

    if st.button("Angebot jetzt annehmen", type="primary", disabled=not widerruf_bestaetigt):
        annahme_neu = {
            "Angebotsnummer": angebotsnummer,
            "Angenommen_Am": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "Bestaetigt_Von": "Kunde (online)",
            "Widerrufsbelehrung_Angezeigt": bool(daten.get("Verbraucher"))
        }
        ok_annahme, meldung_annahme = github_datei_anlegen(
            f"angebote_annahme/{angebotsnummer}/annahme.json",
            json.dumps(annahme_neu, ensure_ascii=False, indent=2).encode("utf-8"),
            f"Angebot {angebotsnummer} online angenommen"
        )
        if ok_annahme:
            st.success("Vielen Dank! Ihre Annahme wurde uebermittelt.")
            st.rerun()
        else:
            st.error(f"Die Annahme konnte nicht uebermittelt werden: {meldung_annahme}")

    zeige_impressum_footer()
    st.stop()


@st.cache_data(ttl=60)
def offene_termine_laden():
    """Holt die Liste der von der Gewerbe-Zentrale angelegten Termin-Vorlagen
    (fuer die Vorausfuellung des Kundendienstberichts). Wird 60 Sekunden lang
    zwischengespeichert, damit nicht bei jedem Tastendruck neu abgerufen wird."""
    eintraege, _ = github_liste("termine")
    termine = []
    for eintrag in eintraege:
        if eintrag.get("type") != "dir":
            continue
        vorlage_bytes, fehler = github_datei_lesen(f"termine/{eintrag['name']}/vorlage.json")
        if fehler or not vorlage_bytes:
            continue
        try:
            vorlage = json.loads(vorlage_bytes.decode("utf-8"))
            vorlage["_termin_id"] = eintrag["name"]
            termine.append(vorlage)
        except Exception:
            continue
    return termine


def bild_komprimieren(foto_bytes):
    """Verkleinert ein Foto auf eine sinnvolle Groesse, damit es sicher per API hochgeladen werden kann."""
    if not PIL_VERFUEGBAR:
        return foto_bytes
    try:
        bild = Image.open(BytesIO(foto_bytes))
        bild = bild.convert("RGB")
        if bild.width > MAX_BILDBREITE:
            neue_hoehe = int(bild.height * (MAX_BILDBREITE / bild.width))
            bild = bild.resize((MAX_BILDBREITE, neue_hoehe))
        puffer = BytesIO()
        bild.save(puffer, format="JPEG", quality=JPEG_QUALITAET)
        return puffer.getvalue()
    except Exception:
        return foto_bytes


# ---------------------------------------------------------------------------
# Oeffentliche Angebotsannahme (kein PIN-Login): wird ueber einen Link mit
# ?modus=angebot&nr=<Angebotsnummer> aufgerufen, den der Kunde von der
# Gewerbe-Zentrale per Mail bekommt. Muss vor dem PIN-Login abgefragt werden,
# da der Kunde (anders als der Handwerker) die PIN nicht kennt.
# ---------------------------------------------------------------------------
_query_modus = st.query_params.get("modus", "")
if _query_modus == "angebot":
    _query_nr = st.query_params.get("nr", "")
    if _query_nr:
        zeige_angebot_annahme(_query_nr)
    else:
        st.error("Kein Angebot angegeben.")
        st.stop()

# ---------------------------------------------------------------------------
# Login (einfacher PIN-Schutz, da die Seite oeffentlich erreichbar ist)
# ---------------------------------------------------------------------------
if "eingeloggt" not in st.session_state:
    st.session_state.eingeloggt = False

if not st.session_state.eingeloggt:
    st.title("Aufmaß-Erfassung")
    st.caption(f"Version {APP_VERSION}")
    pin_eingabe = st.text_input("PIN", type="password", key="login_pin")
    if st.button("Anmelden", type="primary"):
        if pin_eingabe == str(AUFMASS_PIN):
            st.session_state.eingeloggt = True
            st.rerun()
        else:
            st.error("PIN falsch.")
    zeige_impressum_footer()
    st.stop()

# ---------------------------------------------------------------------------
# Modus-Auswahl: Aufmaß oder Kundendienstbericht
# ---------------------------------------------------------------------------
st.title("Vor-Ort-Erfassung")
st.caption(f"Version {APP_VERSION}")

modus = st.radio(
    "Was moechtest du erfassen?",
    ["Aufmaß", "Kundendienstbericht"],
    horizontal=True,
    key="modus_auswahl"
)
st.divider()

# ===========================================================================
# MODUS: AUFMASS
# ===========================================================================
if modus == "Aufmaß":
    st.subheader("Aufmaß-Erfassung")
    st.caption("Daten werden bei 'Aufmaß übermitteln' an die Gewerbe-Zentrale übergeben.")

    if "am_raeume" not in st.session_state:
        st.session_state.am_raeume = [{"name": "Raum 1", "positionen": [], "fotos": [], "audios": []}]

    # Falls eine Terminauswahl weiter unten "Daten uebernehmen" ausgeloest hat, werden
    # die Werte hier - vor dem Erzeugen der Eingabefelder - angewendet (Streamlit
    # verbietet das nachtraegliche Setzen eines bereits instanziierten Widget-Keys).
    if "am_pending_kunde" in st.session_state:
        st.session_state["am_kunde"] = st.session_state.pop("am_pending_kunde")
    if "am_pending_adresse" in st.session_state:
        st.session_state["am_adresse"] = st.session_state.pop("am_pending_adresse")
    if "am_pending_notiz_projekt" in st.session_state:
        st.session_state["am_notiz_projekt"] = st.session_state.pop("am_pending_notiz_projekt")

    st.markdown("**Termin uebernehmen (optional)**")
    st.caption("Wurde der Termin bereits in der Gewerbe-Zentrale angelegt (fuer einen Kunden oder Interessenten), kannst du die Daten hier automatisch uebernehmen.")
    termine_offen_am = offene_termine_laden()
    if not termine_offen_am:
        st.caption("Keine vorausgefuellten Termine gefunden (oder GitHub nicht konfiguriert).")
    else:
        termin_optionen_am = ["Kein Termin - manuell erfassen"] + [
            f"{t.get('datum_einsatz', '')} {t.get('uhrzeit', '')} - {t.get('kunde', '')}" for t in termine_offen_am
        ]
        termin_wahl_am = st.selectbox("Termin auswaehlen", termin_optionen_am, key="am_termin_wahl")
        if termin_wahl_am != "Kein Termin - manuell erfassen":
            if st.button("Daten aus Termin uebernehmen", key="am_termin_uebernehmen_btn"):
                termin_gewaehlt_am = termine_offen_am[termin_optionen_am.index(termin_wahl_am) - 1]
                st.session_state["am_pending_kunde"] = termin_gewaehlt_am.get("kunde", "")
                st.session_state["am_pending_adresse"] = termin_gewaehlt_am.get("adresse", "")
                st.session_state["am_pending_notiz_projekt"] = termin_gewaehlt_am.get("taetigkeit", "")
                st.rerun()

    st.markdown("**Projekt / Baustelle**")
    am_kunde = st.text_input("Kunde / Ansprechpartner", key="am_kunde")
    am_adresse = st.text_input("Adresse der Baustelle", key="am_adresse")
    am_notiz_projekt = st.text_area("Allgemeine Notiz zum Projekt (optional)", key="am_notiz_projekt")

    st.divider()
    st.subheader("Räume")

    for r_idx, raum in enumerate(st.session_state.am_raeume):
        with st.expander(f"{raum['name']}", expanded=True):
            raum["name"] = st.text_input("Raumbezeichnung", value=raum["name"], key=f"am_raum_name_{r_idx}")

            st.markdown("**Positionen (Maße)**")
            for p_idx, pos in enumerate(raum["positionen"]):
                c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                with c1:
                    pos["beschreibung"] = st.text_input("Beschreibung", value=pos["beschreibung"], key=f"am_pos_besch_{r_idx}_{p_idx}")
                with c2:
                    pos["laenge"] = st.number_input("Länge (m)", min_value=0.0, step=0.01, value=float(pos.get("laenge") or 0.0), key=f"am_pos_l_{r_idx}_{p_idx}")
                with c3:
                    pos["breite"] = st.number_input("Breite (m)", min_value=0.0, step=0.01, value=float(pos.get("breite") or 0.0), key=f"am_pos_b_{r_idx}_{p_idx}")
                with c4:
                    pos["menge_manuell"] = st.number_input("oder Stückzahl", min_value=0.0, step=1.0, value=float(pos.get("menge_manuell") or 0.0), key=f"am_pos_stk_{r_idx}_{p_idx}")

            if st.button(f"+ Position in '{raum['name']}'", key=f"am_add_pos_{r_idx}"):
                raum["positionen"].append({"beschreibung": "", "laenge": 0.0, "breite": 0.0, "menge_manuell": 0.0})
                st.rerun()

            st.markdown("**Fotos**")
            st.caption("Foto vorher mit der Kamera-App des Handys aufnehmen und hier hochladen.")
            foto_uploads = st.file_uploader(
                "Foto(s) hochladen",
                type=["jpg", "jpeg", "png", "heic"],
                accept_multiple_files=True,
                key=f"am_foto_{r_idx}"
            )
            if foto_uploads:
                bereits_verarbeitet = st.session_state.get(f"am_foto_verarbeitet_{r_idx}", set())
                neu_hinzugefuegt = 0
                for datei in foto_uploads:
                    kennung = f"{datei.name}_{datei.size}"
                    if kennung in bereits_verarbeitet:
                        continue
                    raum["fotos"].append(bild_komprimieren(datei.getvalue()))
                    bereits_verarbeitet.add(kennung)
                    neu_hinzugefuegt += 1
                st.session_state[f"am_foto_verarbeitet_{r_idx}"] = bereits_verarbeitet
                if neu_hinzugefuegt:
                    st.success(f"{neu_hinzugefuegt} Foto(s) zu '{raum['name']}' hinzugefügt ({len(raum['fotos'])} insgesamt).")

            st.markdown("**Sprachnotiz**")
            st.caption("Tipp: Für mehrere Positionen in einer Aufnahme zwischendurch \"neue Position\" sagen - die Gewerbe-Zentrale trennt den Text dann automatisch auf.")
            audio_aufnahme = st.audio_input("Sprachnotiz aufnehmen", key=f"am_audio_{r_idx}")
            if audio_aufnahme is not None:
                audio_bytes = audio_aufnahme.getvalue()
                kennung_audio = hashlib.md5(audio_bytes).hexdigest()
                bereits_verarbeitet_audio = st.session_state.get(f"am_audio_verarbeitet_{r_idx}")
                if kennung_audio != bereits_verarbeitet_audio:
                    raum["audios"].append(audio_bytes)
                    st.session_state[f"am_audio_verarbeitet_{r_idx}"] = kennung_audio
                    st.success(f"Sprachnotiz zu '{raum['name']}' hinzugefügt ({len(raum['audios'])} insgesamt).")

    col_add_raum, col_remove_raum = st.columns(2)
    with col_add_raum:
        if st.button("+ Weiteren Raum hinzufügen"):
            st.session_state.am_raeume.append({"name": f"Raum {len(st.session_state.am_raeume) + 1}", "positionen": [], "fotos": [], "audios": []})
            st.rerun()
    with col_remove_raum:
        if len(st.session_state.am_raeume) > 1:
            if st.button("- Letzten Raum entfernen"):
                st.session_state.am_raeume.pop()
                st.rerun()

    st.divider()

    if st.button("Aufmaß übermitteln", type="primary"):
        if not am_kunde:
            st.warning("Bitte mindestens den Kunden/Ansprechpartner angeben.")
        else:
            aufmass_id = f"AM-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
            basis_pfad = f"aufmasse/{aufmass_id}"

            raeume_meta = []
            fehler_liste = []
            for r_idx, raum in enumerate(st.session_state.am_raeume):
                foto_namen = []
                for f_idx, foto_bytes in enumerate(raum["fotos"]):
                    dateiname = f"foto_{r_idx + 1}_{f_idx + 1}.jpg"
                    ok, meldung = github_datei_anlegen(f"{basis_pfad}/{dateiname}", foto_bytes, f"Foto zu Aufmaß {aufmass_id}")
                    if ok:
                        foto_namen.append(dateiname)
                    else:
                        fehler_liste.append(f"{dateiname}: {meldung}")

                audio_namen = []
                for a_idx, audio_bytes in enumerate(raum["audios"]):
                    dateiname = f"sprachnotiz_{r_idx + 1}_{a_idx + 1}.wav"
                    ok, meldung = github_datei_anlegen(f"{basis_pfad}/{dateiname}", audio_bytes, f"Sprachnotiz zu Aufmaß {aufmass_id}")
                    if ok:
                        audio_namen.append(dateiname)
                    else:
                        fehler_liste.append(f"{dateiname}: {meldung}")

                raeume_meta.append({
                    "name": raum["name"],
                    "positionen": raum["positionen"],
                    "fotos": foto_namen,
                    "sprachnotizen": audio_namen
                })

            meta = {
                "aufmass_id": aufmass_id,
                "erstellt_am": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "kunde": am_kunde,
                "adresse": am_adresse,
                "notiz_projekt": am_notiz_projekt,
                "raeume": raeume_meta
            }
            meta_bytes = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
            ok_meta, meldung_meta = github_datei_anlegen(f"{basis_pfad}/meta.json", meta_bytes, f"Aufmaß {aufmass_id} erfasst")

            if ok_meta and not fehler_liste:
                st.success(f"Aufmaß {aufmass_id} wurde übermittelt und ist jetzt bereit zum Abholen durch die Gewerbe-Zentrale.")
                st.session_state.am_raeume = [{"name": "Raum 1", "positionen": [], "fotos": [], "audios": []}]
                st.rerun()
            elif ok_meta:
                st.warning(f"Aufmaß {aufmass_id} wurde übermittelt, einzelne Dateien hatten aber Probleme: {'; '.join(fehler_liste)}")
            else:
                st.error(f"Aufmaß konnte nicht übermittelt werden: {meldung_meta}")

# ===========================================================================
# MODUS: KUNDENDIENSTBERICHT
# ===========================================================================
else:
    st.subheader("Kundendienstbericht")
    st.caption("Nach dem Absenden wird der Bericht von der Gewerbe-Zentrale abgeholt und als PDF mit Unterschrift erstellt. Die fortlaufende Berichtsnummer (z. B. KDB-2026-0007) wird dabei automatisch vergeben und erscheint auf dem fertigen PDF.")

    if "kd_fotos" not in st.session_state:
        st.session_state.kd_fotos = []

    # Falls eine Terminauswahl weiter unten "Daten uebernehmen" ausgeloest hat, werden
    # die Werte hier - vor dem Erzeugen der Eingabefelder - angewendet (Streamlit
    # verbietet das nachtraegliche Setzen eines bereits instanziierten Widget-Keys).
    if "kd_pending_kunde" in st.session_state:
        st.session_state["kd_kunde"] = st.session_state.pop("kd_pending_kunde")
    if "kd_pending_adresse" in st.session_state:
        st.session_state["kd_adresse"] = st.session_state.pop("kd_pending_adresse")
    if "kd_pending_taetigkeit" in st.session_state:
        st.session_state["kd_taetigkeit"] = st.session_state.pop("kd_pending_taetigkeit")

    st.markdown("**Termin uebernehmen (optional)**")
    st.caption("Wurde der Termin bereits in der Gewerbe-Zentrale angelegt, kannst du die Daten hier automatisch uebernehmen.")
    termine_offen = offene_termine_laden()
    if not termine_offen:
        st.caption("Keine vorausgefuellten Termine gefunden (oder GitHub nicht konfiguriert).")
    else:
        termin_optionen = ["Kein Termin - manuell erfassen"] + [
            f"{t.get('datum_einsatz', '')} {t.get('uhrzeit', '')} - {t.get('kunde', '')}" for t in termine_offen
        ]
        termin_wahl = st.selectbox("Termin auswaehlen", termin_optionen, key="kd_termin_wahl")
        if termin_wahl != "Kein Termin - manuell erfassen":
            if st.button("Daten aus Termin uebernehmen"):
                termin_gewaehlt = termine_offen[termin_optionen.index(termin_wahl) - 1]
                st.session_state["kd_pending_kunde"] = termin_gewaehlt.get("kunde", "")
                st.session_state["kd_pending_adresse"] = termin_gewaehlt.get("adresse", "")
                st.session_state["kd_pending_taetigkeit"] = termin_gewaehlt.get("taetigkeit", "")
                st.rerun()

    st.markdown("**Kunde / Einsatzort**")
    kd_kunde = st.text_input("Kunde / Ansprechpartner", key="kd_kunde")
    kd_adresse = st.text_input("Adresse des Einsatzortes", key="kd_adresse")
    kd_datum = st.date_input("Datum des Einsatzes", datetime.now(), key="kd_datum")

    st.markdown("**Tätigkeit**")
    kd_taetigkeit = st.text_area(
        "Durchgeführte Arbeiten / Tätigkeitsbeschreibung",
        key="kd_taetigkeit",
        height=150
    )
    kd_material = st.text_area("Verwendetes Material (optional)", key="kd_material")

    st.markdown("**Arbeitszeit**")
    col_beginn, col_ende = st.columns(2)
    with col_beginn:
        kd_beginn = st.time_input("Beginn der Arbeit", datetime.now().replace(second=0, microsecond=0), key="kd_beginn")
    with col_ende:
        kd_ende = st.time_input("Ende der Arbeit", datetime.now().replace(second=0, microsecond=0), key="kd_ende")

    kd_beginn_dt = datetime.combine(datetime.today(), kd_beginn)
    kd_ende_dt = datetime.combine(datetime.today(), kd_ende)
    if kd_ende_dt < kd_beginn_dt:
        kd_ende_dt += timedelta(days=1)
    kd_arbeitszeit = round((kd_ende_dt - kd_beginn_dt).total_seconds() / 3600, 2)
    st.caption(f"Arbeitszeit: {kd_arbeitszeit:g} Stunden")

    st.markdown("**Fotos (optional)**")
    kd_foto_uploads = st.file_uploader(
        "Foto(s) hochladen",
        type=["jpg", "jpeg", "png", "heic"],
        accept_multiple_files=True,
        key="kd_foto_upload"
    )
    if kd_foto_uploads:
        kd_bereits_verarbeitet = st.session_state.get("kd_foto_verarbeitet", set())
        kd_neu = 0
        for datei in kd_foto_uploads:
            kennung = f"{datei.name}_{datei.size}"
            if kennung in kd_bereits_verarbeitet:
                continue
            st.session_state.kd_fotos.append(bild_komprimieren(datei.getvalue()))
            kd_bereits_verarbeitet.add(kennung)
            kd_neu += 1
        st.session_state.kd_foto_verarbeitet = kd_bereits_verarbeitet
        if kd_neu:
            st.success(f"{kd_neu} Foto(s) hinzugefügt ({len(st.session_state.kd_fotos)} insgesamt).")

    st.divider()
    st.markdown("**Unterschrift des Kunden**")
    st.caption("Der Kunde bestätigt hier auf dem Display direkt mit dem Finger oder Stift die ordnungsgemäße Ausführung der Arbeiten.")

    kd_unterschrift_bytes = None
    if CANVAS_VERFUEGBAR:
        kd_canvas_ergebnis = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=3,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=200,
            width=500,
            drawing_mode="freedraw",
            key="kd_unterschrift_canvas"
        )
        if kd_canvas_ergebnis is not None and kd_canvas_ergebnis.image_data is not None:
            try:
                unterschrift_bild = Image.fromarray(kd_canvas_ergebnis.image_data.astype("uint8"), "RGBA")
                unterschrift_bild = unterschrift_bild.convert("RGB")
                unterschrift_puffer = BytesIO()
                unterschrift_bild.save(unterschrift_puffer, format="PNG")
                kd_unterschrift_bytes = unterschrift_puffer.getvalue()
            except Exception:
                kd_unterschrift_bytes = None
        if st.button("Unterschrift löschen"):
            st.session_state.pop("kd_unterschrift_canvas", None)
            st.rerun()
    else:
        st.warning("Die Unterschriftenfläche steht auf diesem Geraet gerade nicht zur Verfuegung (Baustein 'streamlit-drawable-canvas' fehlt). Der Bericht kann trotzdem ohne Unterschrift übermittelt werden.")

    st.divider()

    if st.button("Kundendienstbericht übermitteln", type="primary"):
        if not kd_kunde or not kd_taetigkeit:
            st.warning("Bitte mindestens Kunde und Tätigkeitsbeschreibung angeben.")
        else:
            bericht_id = f"KD-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
            basis_pfad_kd = f"kundendienst/{bericht_id}"

            foto_namen_kd = []
            fehler_liste_kd = []
            for f_idx, foto_bytes in enumerate(st.session_state.kd_fotos):
                dateiname = f"foto_{f_idx + 1}.jpg"
                ok, meldung = github_datei_anlegen(f"{basis_pfad_kd}/{dateiname}", foto_bytes, f"Foto zu Kundendienstbericht {bericht_id}")
                if ok:
                    foto_namen_kd.append(dateiname)
                else:
                    fehler_liste_kd.append(f"{dateiname}: {meldung}")

            unterschrift_dateiname = None
            if kd_unterschrift_bytes:
                ok_us, meldung_us = github_datei_anlegen(f"{basis_pfad_kd}/unterschrift.png", kd_unterschrift_bytes, f"Unterschrift zu Kundendienstbericht {bericht_id}")
                if ok_us:
                    unterschrift_dateiname = "unterschrift.png"
                else:
                    fehler_liste_kd.append(f"unterschrift.png: {meldung_us}")

            meta_kd = {
                "bericht_id": bericht_id,
                "erstellt_am": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "kunde": kd_kunde,
                "adresse": kd_adresse,
                "datum_einsatz": kd_datum.strftime("%d.%m.%Y"),
                "taetigkeit": kd_taetigkeit,
                "material": kd_material,
                "beginn": kd_beginn.strftime("%H:%M"),
                "ende": kd_ende.strftime("%H:%M"),
                "arbeitszeit_stunden": kd_arbeitszeit,
                "fotos": foto_namen_kd,
                "unterschrift": unterschrift_dateiname
            }
            meta_bytes_kd = json.dumps(meta_kd, ensure_ascii=False, indent=2).encode("utf-8")
            ok_meta_kd, meldung_meta_kd = github_datei_anlegen(f"{basis_pfad_kd}/meta.json", meta_bytes_kd, f"Kundendienstbericht {bericht_id} erfasst")

            if ok_meta_kd and not fehler_liste_kd:
                st.success(f"Kundendienstbericht {bericht_id} wurde übermittelt und ist jetzt bereit zum Abholen durch die Gewerbe-Zentrale.")
                st.session_state.kd_fotos = []
                st.session_state.pop("kd_foto_verarbeitet", None)
                st.session_state.pop("kd_unterschrift_canvas", None)
                st.rerun()
            elif ok_meta_kd:
                st.warning(f"Kundendienstbericht {bericht_id} wurde übermittelt, einzelne Dateien hatten aber Probleme: {'; '.join(fehler_liste_kd)}")
            else:
                st.error(f"Kundendienstbericht konnte nicht übermittelt werden: {meldung_meta_kd}")

st.divider()
if st.button("Abmelden"):
    st.session_state.eingeloggt = False
    st.rerun()

zeige_impressum_footer()
