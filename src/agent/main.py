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

def main():
    print("=" * 65)
    print("   JOB AGENT AI - BÚSQUEDA AUTENTICADA CON COOKIE DE LINKEDIN   ")
    print("=" * 65)

    manager = DataManager()
    profile = manager.load_profile()
    applied_jobs = manager.load_applied_jobs()

    print(f"[*] Perfil de Usuario: {profile.get('user_name', 'Usuario')}")
    if os.environ.get("LINKEDIN_COOKIE"):
        print("[*] Sesión de LinkedIn: Autenticada con Cookie de Sesión (li_at) ✅")
    else:
        print("[!] Sesión de LinkedIn: Modo Invitado (Sin cookie)")

    matcher = JobMatcher(profile=profile, applied_jobs=applied_jobs)
    print(f"[*] Postulaciones consideradas (últimos 6 meses): {len(matcher.recent_applied)}")

    search_keywords = list(profile.get("search_keywords", []))
    for app in matcher.recent_applied:
        title = app.get("title")
        if title and title not in search_keywords:
            search_keywords.append(title)

    print(f"[*] Consultando LinkedIn con {len(search_keywords)} patrones de búsqueda...")

    scraper = LinkedInScraper()
    discovered_jobs = []

    locations = profile.get("preferred_locations", ["Chile"])
    primary_location = locations[0] if locations else "Chile"

    for kw in search_keywords[:5]:
        jobs = scraper.search_jobs(keyword=kw, location=primary_location, limit=5)
        discovered_jobs.extend(jobs)

    all_jobs = manager.merge_discovered_jobs(discovered_jobs)

    scored_jobs = matcher.process_jobs(all_jobs)
    manager.save_jobs(scored_jobs)

    print("\n" + "-" * 65)
    print(f"[+] Proceso completado exitosamente.")
    print(f"[+] Total de empleos procesados en base de datos: {len(scored_jobs)}")

    print("\n--- TOP EMPLEOS RECOMENDADOS CON TU SESIÓN DE LINKEDIN ---")
    for idx, job in enumerate(scored_jobs[:5], 1):
        print(f"{idx}. [{job.get('match_score')}% Match] {job.get('title')} en {job.get('company')}")
        print(f"   Ubicación: {job.get('location')}")
        print(f"   URL: {job.get('url')}")
        print(f"   Razones: {', '.join(job.get('match_reasons', []))}")
        print()

if __name__ == "__main__":
    main()
