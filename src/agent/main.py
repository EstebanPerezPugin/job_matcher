import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno locales (.env)
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.agent.data_manager import DataManager
from src.agent.matcher import JobMatcher
from src.agent.linkedin_scraper import LinkedInScraper
from src.agent.linkedin_applied_scraper import LinkedInAppliedScraper

def sync_applied_from_linkedin():
    """Importa las postulaciones reales desde LinkedIn Jobs Tracker."""
    print("\n[*] Sincronizando postulaciones desde LinkedIn Jobs Tracker...")
    scraper = LinkedInAppliedScraper()
    new_jobs = scraper.scrape()

    if new_jobs:
        merged = scraper.merge_with_existing(new_jobs)
        print(f"[*] Total de postulaciones en historial: {len(merged)}")
        return merged
    else:
        print("[!] No se pudieron sincronizar postulaciones. Usando historial local.")
        return None

def main(sync_applied: bool = False):
    print("=" * 65)
    print("   JOB AGENT AI - BÚSQUEDA AUTENTICADA CON COOKIE DE LINKEDIN   ")
    print("=" * 65)

    manager = DataManager()
    profile = manager.load_profile()

    if os.environ.get("LINKEDIN_COOKIE"):
        print("[*] Sesión de LinkedIn: Autenticada con Cookie de Sesión (li_at) ✅")
    else:
        print("[!] Sesión de LinkedIn: Modo Invitado (Sin cookie)")

    # 1. Sincronizar postulaciones desde LinkedIn si se solicita
    if sync_applied:
        sync_applied_from_linkedin()

    applied_jobs = manager.load_applied_jobs()

    print(f"[*] Perfil de Usuario: {profile.get('user_name', 'Usuario')}")
    print(f"[*] Postulaciones en historial: {len(applied_jobs)}")

    # 2. Inicializar matcher con postulaciones de los últimos 6 meses
    matcher = JobMatcher(profile=profile, applied_jobs=applied_jobs)
    print(f"[*] Postulaciones consideradas (últimos 6 meses): {len(matcher.recent_applied)}")

    if matcher.learned_keywords:
        print(f"[*] Palabras clave aprendidas: {', '.join(matcher.learned_keywords[:10])}")

    # 3. Construir búsquedas dinámicas basadas en postulaciones recientes
    search_keywords = list(profile.get("search_keywords", []))
    for app in matcher.recent_applied:
        title = app.get("title")
        if title and title not in search_keywords:
            search_keywords.append(title)

    print(f"[*] Consultando LinkedIn con {len(search_keywords[:5])} patrones de búsqueda...")

    # 4. Buscar nuevas vacantes en LinkedIn
    scraper = LinkedInScraper()
    discovered_jobs = []

    locations = profile.get("preferred_locations", ["Chile"])
    primary_location = locations[0] if locations else "Chile"

    for kw in search_keywords[:5]:
        jobs = scraper.search_jobs(keyword=kw, location=primary_location, limit=5)
        discovered_jobs.extend(jobs)

    # 5. Fusionar y puntuar
    all_jobs = manager.merge_discovered_jobs(discovered_jobs)
    scored_jobs = matcher.process_jobs(all_jobs)
    manager.save_jobs(scored_jobs)

    print("\n" + "-" * 65)
    print(f"[+] Proceso completado. {len(scored_jobs)} empleos procesados.")

    print("\n--- TOP EMPLEOS RECOMENDADOS ---")
    for idx, job in enumerate(scored_jobs[:5], 1):
        print(f"{idx}. [{job.get('match_score')}% Match] {job.get('title')} en {job.get('company')}")
        print(f"   URL: {job.get('url')}")
        print()

if __name__ == "__main__":
    # Si se pasa --sync-applied, primero sincroniza postulaciones desde LinkedIn
    sync = "--sync-applied" in sys.argv
    main(sync_applied=sync)
