import time
import datetime
from dateutil.utils import today
from dateutil.relativedelta import relativedelta, MO  # MO = Monday
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

# -----------------------------------------------------------------
# CONFIGURATION À ADAPTER
# -----------------------------------------------------------------
URL_LOGIN = "https://ws-edt-cd.wigorservices.net/Login.aspx"
USERNAME = "USERNAME"
PASSWORD = "PASSWORD"

# URL de base du planning. On y insérera la date au format M/D/YYYY (ou D/M/YYYY).
# Par exemple : "action=posEDTLMS" ou "action=posEDTJour" selon ta config
URL_TEMPLATE = (
    "https://ws-edt-cd.wigorservices.net/"
    "WebPsDyn.aspx?action=posEDTLMS&serverID=C&Tel=lelia.kozan&date={date}"
    "&hashURL=..."
)

# Classes CSS qu'on suppose dans le code Wigor
CSS_COURS   = "td.TCase"     # Nom du cours
CSS_SALLE   = "td.TCSalle"   # Salle
CSS_DEBUT   = "td.TChdeb"    # Heure début
CSS_FIN     = "td.TChfin"    # Heure fin
CSS_PROF    = "td.TCProf"    # Prof
CSS_TEAMS   = "div.Teams a"  # Lien Teams, ex: <div class="Teams"><a href="...">Teams</a></div>

def get_monday_of_current_week():
    """
    Renvoie la date (objet datetime.date) du lundi de la semaine en cours.
    Ex : si on est mardi 28, on obtient lundi 27.
    """
    d = today().date()
    # Avec dateutil, on prend "lundi" de la semaine en cours
    monday = d + relativedelta(weekday=MO(-1))
    return monday

def build_url_for_date(dt: datetime.date):
    """
    Construit l'URL Wigor en insérant la date au bon format.
    
    Selon ta configuration Wigor, 
    - Soit c'est M/D/YYYY
    - Soit c'est D/M/YYYY
    
    Ici, on suppose M/D/YYYY.
    """
    date_str = f"{dt.month}/{dt.day}/{dt.year}"
    return URL_TEMPLATE.format(date=date_str)

def parse_courses(html: str):
    """
    Analyse le HTML de la page et retourne une liste de dictionnaires
    contenant les infos de chaque cours.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Chaque "case de cours" peut être une <tr>, ou un ensemble de <td> 
    # regroupés dans un <tr>. 
    # Selon ton Wigor, il peut y avoir <tr class="LigneEdt"> ...
    # On fait un exemple : 
    # la "ligne de cours" serait un <tr> qui contient TCase, TCSalle, TChdeb...
    
    # 1) Récupérer chaque ligne. Souvent un <tr> 
    #    => On cherche un identifiant commun. 
    #    Parfois, <tr> n'a pas de classe, il faut s'adapter.
    rows = soup.select("tr")  # ou "tr.LigneEdt" si c'est le cas
    
    all_cours = []
    for row in rows:
        # 2) Dans chaque ligne, on cherche la cellule TCase (nom du cours)
        td_cours = row.select_one(CSS_COURS)
        if not td_cours:
            # Pas de cours dans cette ligne -> on skip
            continue
        
        # Récupère le nom du cours (ex: "HEP COOPERATION")
        nom_cours = td_cours.get_text(strip=True)
        
        # Récupère la salle
        td_salle = row.select_one(CSS_SALLE)
        salle = td_salle.get_text(strip=True) if td_salle else ""
        
        # Récupère l'heure début
        td_debut = row.select_one(CSS_DEBUT)
        heure_debut = td_debut.get_text(strip=True) if td_debut else ""
        
        # Récupère l'heure fin
        td_fin = row.select_one(CSS_FIN)
        heure_fin = td_fin.get_text(strip=True) if td_fin else ""
        
        # Récupère le prof
        td_prof = row.select_one(CSS_PROF)
        prof = td_prof.get_text(strip=True) if td_prof else ""
        
        # Récupère le lien Teams
        # Souvent un <div class="Teams"><a href="URL">Teams</a></div>
        a_teams = row.select_one(CSS_TEAMS)
        lien_teams = a_teams["href"] if a_teams and a_teams.has_attr("href") else ""
        
        # On stocke toutes les infos dans un dict
        cours_info = {
            "nom_cours": nom_cours,
            "heure_debut": heure_debut,
            "heure_fin": heure_fin,
            "salle": salle,
            "prof": prof,
            "teams": lien_teams
        }
        all_cours.append(cours_info)
    
    return all_cours

def main():
    # 1) Calcule la date du lundi de la semaine en cours
    monday = get_monday_of_current_week()
    # 2) On fera un parsing pour chaque jour de la semaine (lundi -> dimanche)
    days_of_week = [monday + datetime.timedelta(days=i) for i in range(7)]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 3) Se connecter
        page.goto(URL_LOGIN)
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        all_cours_week = []
        
        # 4) Parcours les 7 jours de la semaine
        for day in days_of_week:
            url = build_url_for_date(day)
            page.goto(url)
            page.wait_for_load_state("networkidle")
            time.sleep(2)  # Laisse le temps au JS d'insérer les TD
            
            # Optionnel : si tu dois cliquer sur un bouton "Vue journalière" ou "Semaine"
            # page.click("button#jour")  # par exemple
            # time.sleep(1)
            
            # Récupère le HTML
            html = page.content()
            cours_list = parse_courses(html)
            
            # On ajoute la date du jour à chaque cours
            for c in cours_list:
                # date du jour
                c["date"] = day.isoformat()
            
            all_cours_week.extend(cours_list)
        
        browser.close()
    
    # 5) Affiche le résultat
    print("=== COURS DE LA SEMAINE EN COURS ===\n")
    for c in all_cours_week:
        print(
            f"- {c['date']} : {c['heure_debut']} - {c['heure_fin']} | {c['nom_cours']} "
            f"(Salle: {c['salle']}, Prof: {c['prof']}, Teams: {c['teams']})"
        )

if __name__ == "__main__":
    main()
