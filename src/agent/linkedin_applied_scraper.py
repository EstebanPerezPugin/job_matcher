import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LINKEDIN_TRACKER_URL = "https://www.linkedin.com/jobs-tracker/?stage=applied"

class LinkedInAppliedScraper:
    """
    Extrae las postulaciones reales desde la página de seguimiento de LinkedIn.
    Utiliza Playwright con la cookie li_at para autenticación.
    """

    def __init__(self, cookie: str = None):
        self.cookie = cookie or os.environ.get("LINKEDIN_COOKIE", "")

    async def _scrape_async(self) -> List[Dict[str, Any]]:
        if not self.cookie:
            print("[AppliedScraper] ⚠️  No se encontró LINKEDIN_COOKIE. Revisa tu archivo .env")
            return []

        applied_jobs = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="es-ES",
                viewport={"width": 1280, "height": 900}
            )

            # Establecer cookie de sesión li_at
            await context.add_cookies([{
                "name": "li_at",
                "value": self.cookie,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True
            }])

            page = await context.new_page()

            print(f"[AppliedScraper] Navegando a: {LINKEDIN_TRACKER_URL}")
            await page.goto(LINKEDIN_TRACKER_URL, wait_until="domcontentloaded", timeout=30000)

            # Esperar a que se cargue la lista de aplicaciones
            try:
                await page.wait_for_selector(
                    "ul.jobs-tracker__list, [data-testid='jobs-tracker-card'], .job-card-container, .jobs-applied-jobs-list",
                    timeout=15000
                )
            except Exception:
                print("[AppliedScraper] El selector primario no apareció. Esperando renderizado alternativo...")
                await page.wait_for_timeout(4000)

            # Hacer scroll para cargar tarjetas lazy-loaded
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 600)")
                await page.wait_for_timeout(800)

            # Extraer el contenido completo de la página para parsear
            content = await page.content()

            # Intentar extraer datos estructurados de múltiples selectores posibles
            applied_jobs = await self._extract_jobs_from_page(page)

            if not applied_jobs:
                print("[AppliedScraper] No se encontraron tarjetas con selectores específicos.")
                print("[AppliedScraper] Guardando captura de depuración en data/debug_applied_page.html")
                debug_path = DATA_DIR / "debug_applied_page.html"
                debug_path.write_text(content, encoding="utf-8")

            await browser.close()

        return applied_jobs

    async def _extract_jobs_from_page(self, page) -> List[Dict[str, Any]]:
        """Intenta múltiples estrategias de extracción para adaptarse al DOM de LinkedIn."""
        jobs = []

        # Estrategia 1: Tarjetas del jobs tracker
        try:
            cards = await page.query_selector_all(
                "li.jobs-tracker__list-item, [data-testid='job-card'], .job-card-container"
            )
            print(f"[AppliedScraper] Estrategia 1: encontradas {len(cards)} tarjetas")

            for card in cards:
                try:
                    title_el = await card.query_selector(".job-card-list__title, .job-card-container__link strong, h3")
                    company_el = await card.query_selector(".job-card-container__company-name, .artdeco-entity-lockup__subtitle")
                    location_el = await card.query_selector(".job-card-container__metadata-item, .job-card-container__metadata-wrapper li")
                    link_el = await card.query_selector("a.job-card-list__title, a.job-card-container__link, a[href*='/jobs/view/']")
                    date_el = await card.query_selector("time, .job-card-container__footer-item, .jobs-tracker__application-date")

                    title = await title_el.inner_text() if title_el else "Sin título"
                    company = await company_el.inner_text() if company_el else "Sin empresa"
                    location = await location_el.inner_text() if location_el else "No especificada"
                    url = await link_el.get_attribute("href") if link_el else "#"
                    date_text = await date_el.inner_text() if date_el else ""

                    if url and not url.startswith("http"):
                        url = "https://www.linkedin.com" + url

                    job = self._build_job_record(title, company, location, url, date_text)
                    jobs.append(job)
                except Exception as e:
                    print(f"[AppliedScraper] Error extrayendo tarjeta: {e}")
                    continue

        except Exception as e:
            print(f"[AppliedScraper] Estrategia 1 falló: {e}")

        if jobs:
            return jobs

        # Estrategia 2: Buscar por aria-label y links de trabajos
        try:
            links = await page.query_selector_all("a[href*='/jobs/view/']")
            print(f"[AppliedScraper] Estrategia 2: encontrados {len(links)} links de empleos")
            seen_urls = set()

            for link in links:
                try:
                    href = await link.get_attribute("href") or "#"
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    if not href.startswith("http"):
                        href = "https://www.linkedin.com" + href

                    text = await link.inner_text()
                    if not text.strip():
                        continue

                    # Buscar empresa en el contenedor padre
                    parent = await link.evaluate_handle("el => el.closest('.job-card-container, li, article, div[class*=\"job\"]')")
                    company_el = await parent.query_selector(".artdeco-entity-lockup__subtitle, .job-card-container__company-name, h4") if parent else None
                    company = await company_el.inner_text() if company_el else "Sin empresa"

                    job = self._build_job_record(text.strip(), company.strip(), "Chile", href, "")
                    jobs.append(job)
                except Exception:
                    continue

        except Exception as e:
            print(f"[AppliedScraper] Estrategia 2 falló: {e}")

        return jobs

    def _build_job_record(self, title: str, company: str, location: str, url: str, date_str: str) -> Dict[str, Any]:
        """Construye un registro de postulación normalizado."""
        # Intentar parsear la fecha o usar la fecha de hoy
        applied_date = datetime.today().strftime("%Y-%m-%d")
        if date_str:
            # Buscar patrones de fecha en el string
            match = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
            if match:
                applied_date = match.group(1)

        # Extraer skills básicos del título
        skills = self._infer_skills_from_title(title)

        return {
            "id": f"li-applied-{hash(url) & 0xffffff:06x}",
            "title": title.strip(),
            "company": company.strip(),
            "location": location.strip(),
            "url": url.strip(),
            "applied_date": applied_date,
            "status": "Postulado",
            "notes": "Importado automáticamente desde LinkedIn Jobs Tracker",
            "description": f"Postulación a {title} en {company}.",
            "skills": skills,
            "source": "linkedin_tracker"
        }

    def _infer_skills_from_title(self, title: str) -> List[str]:
        t = title.lower()
        skills = []
        if "python" in t: skills.append("Python")
        if "react" in t: skills.append("React")
        if "full stack" in t or "fullstack" in t: skills.extend(["React", "Node.js"])
        if "backend" in t: skills.extend(["Python", "SQL"])
        if "frontend" in t: skills.extend(["JavaScript", "React"])
        if "data" in t: skills.extend(["Python", "SQL"])
        if "ai" in t or "ml" in t or "machine learning" in t: skills.extend(["Python", "Machine Learning"])
        if "java" in t and "javascript" not in t: skills.append("Java")
        if "node" in t: skills.append("Node.js")
        if "devops" in t or "cloud" in t: skills.extend(["Docker", "AWS"])
        if not skills:
            skills = ["Software Development", "Git"]
        return list(dict.fromkeys(skills))  # Deduplicate preserving order

    def scrape(self) -> List[Dict[str, Any]]:
        """Punto de entrada síncrono para ejecutar el scraper de postulaciones."""
        return asyncio.run(self._scrape_async())

    def merge_with_existing(self, new_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fusiona las postulaciones importadas con las existentes, sin duplicar."""
        applied_path = DATA_DIR / "applied.json"
        existing = []
        if applied_path.exists():
            with open(applied_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        existing_urls = {j.get("url") for j in existing if j.get("url")}
        existing_ids = {j.get("id") for j in existing if j.get("id")}
        added_count = 0

        for job in new_jobs:
            if job["url"] in existing_urls or job["id"] in existing_ids:
                continue
            existing.insert(0, job)
            added_count += 1

        print(f"[AppliedScraper] ✅ {added_count} postulaciones nuevas importadas desde LinkedIn.")

        with open(applied_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        return existing
