import sys
import os
from pathlib import Path

# Permitir importaciones relativas
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.agent.data_manager import DataManager
from src.agent.matcher import JobMatcher
from src.agent.linkedin_scraper import LinkedInScraper

def main():
    print("=" * 60)
    print("   AGENTE DE BÚSQUEDA DE EMPLEOS & APRENDIZAJE AUTOMÁTICO   ")
    print("=" * 60)

    manager = DataManager()
    profile = manager.load_profile()
    applied_jobs = manager.load_applied_jobs()

    print(f"[*] Perfil de usuario: {profile.get('user_name', 'Usuario')}")
    print(f"[*] Postulaciones previas registradas: {len(applied_jobs)}")
    print(f"[*] Palabras clave de búsqueda: {', '.join(profile.get('search_keywords', []))}")

    # Inicializar motor de IA / Matcher
    matcher = JobMatcher(profile=profile, applied_jobs=applied_jobs)
    if matcher.learned_keywords:
        print(f"[*] Palabras clave aprendidas de postulaciones pasadas: {', '.join(matcher.learned_keywords[:8])}")

    # Scraper
    scraper = LinkedInScraper()
    discovered_jobs = []

    locations = profile.get("preferred_locations", ["Chile"])
    primary_location = locations[0] if locations else "Chile"

    for keyword in profile.get("search_keywords", ["Software Engineer"]):
        jobs = scraper.search_jobs(keyword=keyword, location=primary_location, limit=5)
        discovered_jobs.extend(jobs)

    # Fusionar con los empleos ya guardados en jobs.json
    all_jobs = manager.merge_discovered_jobs(discovered_jobs)

    # Ejecutar puntuación de match para todas las ofertas
    scored_jobs = matcher.process_jobs(all_jobs)
    manager.save_jobs(scored_jobs)

    print("\n" + "-" * 60)
    print(f"[+] Proceso completado exitosamente.")
    print(f"[+] Total de empleos en la base de datos: {len(scored_jobs)}")
    
    print("\n--- TOP 3 MEJORES VACANTES ENCONTRADAS ---")
    for job in scored_jobs[:3]:
        print(f"• [{job.get('match_score')}% Match] {job.get('title')} en {job.get('company')}")
        print(f"  URL: {job.get('url')}")
        print(f"  Razones: {', '.join(job.get('match_reasons', []))}")
        print()

if __name__ == "__main__":
    main()
