import streamlit as st
import requests
import base64
import json
import uuid
from datetime import datetime
from io import BytesIO

try:
    from PIL import Image
    PIL_VERFUEGBAR = True
except Exception:
    PIL_VERFUEGBAR = False

st.set_page_config(page_title="Aufmaß-Erfassung", layout="centered")

APP_VERSION = "1.1.0"

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
    st.stop()

# ---------------------------------------------------------------------------
# Aufmaß-Erfassung
# ---------------------------------------------------------------------------
st.title("Aufmaß-Erfassung")
st.caption(f"Version {APP_VERSION} - Daten werden bei 'Aufmaß übermitteln' an die Gewerbe-Zentrale übergeben.")

if "am_raeume" not in st.session_state:
    st.session_state.am_raeume = [{"name": "Raum 1", "positionen": [], "fotos": [], "audios": []}]

st.subheader("Projekt / Baustelle")
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
        audio_aufnahme = st.audio_input("Sprachnotiz aufnehmen", key=f"am_audio_{r_idx}")
        if audio_aufnahme is not None:
            raum["audios"].append(audio_aufnahme.getvalue())
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

st.divider()
if st.button("Abmelden"):
    st.session_state.eingeloggt = False
    st.rerun()
