import asyncio
import json
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# URL con filtro de última semana — LinkedIn la ordena de más nueva a más antigua
LINKEDIN_TRACKER_URL = "https://www.linkedin.com/jobs-tracker/?stage=applied&dateFilter=past_week"


class LinkedInAppliedScraper:
    """
    Extrae las postulaciones reales desde LinkedIn Jobs Tracker (stage=applied)
    usando Playwright con la cookie li_at para autenticación.
    Ordena de más reciente a más antigua.
    """

    def __init__(self, cookie: str = None):
        self.cookie = cookie or os.environ.get("LINKEDIN_COOKIE", "")

    # ------------------------------------------------------------------ #
    # Entrypoints                                                          #
    # ------------------------------------------------------------------ #

    def scrape(self) -> List[Dict[str, Any]]:
        """Punto de entrada síncrono."""
        return asyncio.run(self._scrape_async())

    def merge_with_existing(self, new_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fusiona los trabajos importados con el historial existente (sin duplicar)
        y ordena todo de más reciente a más antiguo.
        """
        applied_path = DATA_DIR / "applied.json"
        existing: List[Dict[str, Any]] = []
        if applied_path.exists():
            with open(applied_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        existing_urls = {j.get("url") for j in existing if j.get("url")}
        existing_ids  = {j.get("id")  for j in existing if j.get("id")}
        added_count = 0

        for job in new_jobs:
            if job["url"] in existing_urls or job["id"] in existing_ids:
                continue
            existing.append(job)
            added_count += 1

        # Ordenar de más reciente a más antigua
        existing = self._sort_by_date(existing)

        print(f"[AppliedScraper] ✅ {added_count} postulaciones nuevas importadas desde LinkedIn.")

        with open(applied_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        return existing

    # ------------------------------------------------------------------ #
    # Sorting                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _sort_by_date(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ordena de más reciente (mayor fecha) a más antigua."""
        def sort_key(j: Dict[str, Any]) -> str:
            d = j.get("applied_date", "1970-01-01")
            # Mantener orden secundario por id para empates
            return d + j.get("id", "")
        return sorted(jobs, key=sort_key, reverse=True)

    # ------------------------------------------------------------------ #
    # Core scraping                                                        #
    # ------------------------------------------------------------------ #

    async def _scrape_async(self) -> List[Dict[str, Any]]:
        if not self.cookie:
            print("[AppliedScraper] ⚠️  No se encontró LINKEDIN_COOKIE. Revisa tu archivo .env")
            return []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="es-ES",
                viewport={"width": 1440, "height": 900},
            )

            # Inyectar cookie de sesión
            await context.add_cookies([{
                "name": "li_at",
                "value": self.cookie,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }])

            page = await context.new_page()
            print(f"[AppliedScraper] 🌐 Navegando a: {LINKEDIN_TRACKER_URL}")
            await page.goto(LINKEDIN_TRACKER_URL, wait_until="domcontentloaded", timeout=30000)

            # Esperar a que la SPA de LinkedIn renderice el contenido
            await self._wait_for_content(page)

            # Scroll progresivo para forzar carga lazy
            await self._scroll_all(page)

            # Guardar HTML de debug siempre (útil para diagnosticar cambios en el DOM)
            content = await page.content()
            debug_path = DATA_DIR / "debug_applied_page.html"
            debug_path.write_text(content, encoding="utf-8")

            # Extraer trabajos
            jobs = await self._extract_jobs(page)

            if not jobs:
                print("[AppliedScraper] ⚠️ No se extrajeron trabajos. Revisa debug_applied_page.html")

            await browser.close()

        # Ordenar ya en el retorno de más reciente a más antigua
        return self._sort_by_date(jobs)

    async def _wait_for_content(self, page) -> None:
        selectors = [
            "ul.jobs-tracker__list",
            "[data-testid='job-card']",
            ".job-card-container",
            ".jobs-applied-jobs-list",
            "a[href*='/jobs/view/']",
        ]
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=8000)
                print(f"[AppliedScraper] ✓ Contenido detectado con selector: {sel}")
                return
            except Exception:
                continue
        print("[AppliedScraper] Ningún selector rápido encontrado, esperando 5s...")
        await page.wait_for_timeout(5000)

    async def _scroll_all(self, page) -> None:
        """Scroll suave hacia abajo para activar carga lazy."""
        for i in range(5):
            await page.evaluate(f"window.scrollBy(0, {600 + i * 100})")
            await page.wait_for_timeout(600)
        # Volver al inicio para que el DOM esté estable
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(400)

    # ------------------------------------------------------------------ #
    # Extraction strategies                                                #
    # ------------------------------------------------------------------ #

    async def _extract_jobs(self, page) -> List[Dict[str, Any]]:
        """Intenta múltiples estrategias de extracción y devuelve la que más resultados da."""
        results_s1 = await self._strategy_card_elements(page)
        if results_s1:
            print(f"[AppliedScraper] Estrategia 1 exitosa: {len(results_s1)} trabajos")
            return results_s1

        results_s2 = await self._strategy_job_links(page)
        if results_s2:
            print(f"[AppliedScraper] Estrategia 2 exitosa: {len(results_s2)} trabajos")
            return results_s2

        results_s3 = await self._strategy_json_ld(page)
        if results_s3:
            print(f"[AppliedScraper] Estrategia 3 exitosa: {len(results_s3)} trabajos")
            return results_s3

        return []

    async def _strategy_card_elements(self, page) -> List[Dict[str, Any]]:
        """Estrategia 1: Seleccionar tarjetas de empleo del DOM."""
        jobs = []
        card_selectors = [
            "li.jobs-tracker__list-item",
            "[data-testid='job-card']",
            ".job-card-container",
            "li.scaffold-layout__list-item",
        ]

        cards = []
        for sel in card_selectors:
            try:
                cards = await page.query_selector_all(sel)
                if cards:
                    print(f"[AppliedScraper] S1: {len(cards)} tarjetas con '{sel}'")
                    break
            except Exception:
                continue

        for card in cards:
            try:
                title    = await self._get_text(card, [
                    ".job-card-list__title strong",
                    ".job-card-container__link strong",
                    "a[href*='/jobs/view/'] strong",
                    "h3", "h2",
                ])
                company  = await self._get_text(card, [
                    ".job-card-container__company-name",
                    ".artdeco-entity-lockup__subtitle",
                    ".job-card-container__primary-description",
                    "h4",
                ])
                location = await self._get_text(card, [
                    ".job-card-container__metadata-item",
                    ".artdeco-entity-lockup__caption",
                    "li.job-card-container__metadata-wrapper li",
                ])
                date_str = await self._get_date_text(card)
                url      = await self._get_href(card, [
                    "a.job-card-list__title",
                    "a.job-card-container__link",
                    "a[href*='/jobs/view/']",
                ])

                if not title or title == "Sin título":
                    continue

                jobs.append(self._build_record(title, company, location, url, date_str))
            except Exception as e:
                print(f"[AppliedScraper] Error en tarjeta: {e}")
                continue

        return jobs

    async def _strategy_job_links(self, page) -> List[Dict[str, Any]]:
        """Estrategia 2: Recolectar todos los <a href*='/jobs/view/'> únicos."""
        jobs = []
        seen_urls: set = set()

        links = await page.query_selector_all("a[href*='/jobs/view/']")
        print(f"[AppliedScraper] S2: {len(links)} links de empleos encontrados")

        for link in links:
            try:
                href = await link.get_attribute("href") or ""
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)
                if not href.startswith("http"):
                    href = "https://www.linkedin.com" + href

                title = (await link.inner_text()).strip()
                if not title:
                    continue

                # Intentar obtener contexto del contenedor
                company  = ""
                location = ""
                date_str = ""
                try:
                    parent = await link.evaluate_handle(
                        "el => el.closest('.job-card-container, li, article')"
                    )
                    if parent:
                        company  = await self._get_text(parent, [
                            ".job-card-container__company-name",
                            ".artdeco-entity-lockup__subtitle", "h4",
                        ])
                        location = await self._get_text(parent, [
                            ".job-card-container__metadata-item",
                            ".artdeco-entity-lockup__caption",
                        ])
                        date_str = await self._get_date_text(parent)
                except Exception:
                    pass

                jobs.append(self._build_record(title, company, location, href, date_str))
            except Exception:
                continue

        return jobs

    async def _strategy_json_ld(self, page) -> List[Dict[str, Any]]:
        """Estrategia 3: Intentar extraer datos de JSON-LD en el <head>."""
        jobs = []
        try:
            scripts = await page.query_selector_all("script[type='application/ld+json']")
            for script in scripts:
                raw = await script.inner_text()
                data = json.loads(raw)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "JobPosting":
                        title    = item.get("title", "Sin título")
                        company  = item.get("hiringOrganization", {}).get("name", "")
                        location = item.get("jobLocation", {}).get("address", {}).get("addressLocality", "")
                        url      = item.get("url", "#")
                        date_str = item.get("datePosted", "")
                        jobs.append(self._build_record(title, company, location, url, date_str))
        except Exception as e:
            print(f"[AppliedScraper] S3 JSON-LD falló: {e}")
        return jobs

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    async def _get_text(self, element, selectors: List[str]) -> str:
        for sel in selectors:
            try:
                el = await element.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                continue
        return ""

    async def _get_href(self, element, selectors: List[str]) -> str:
        for sel in selectors:
            try:
                el = await element.query_selector(sel)
                if el:
                    href = await el.get_attribute("href") or ""
                    if href:
                        if not href.startswith("http"):
                            href = "https://www.linkedin.com" + href
                        return href
            except Exception:
                continue
        return "#"

    async def _get_date_text(self, element) -> str:
        """Extrae texto de fecha desde múltiples posibles elementos."""
        date_selectors = [
            "time",
            ".jobs-tracker__application-date",
            ".job-card-container__footer-item",
            "[class*='date']",
            "[class*='time']",
        ]
        for sel in date_selectors:
            try:
                el = await element.query_selector(sel)
                if el:
                    # Intentar atributo datetime primero
                    dt_attr = await el.get_attribute("datetime") or ""
                    if dt_attr:
                        return dt_attr
                    text = (await el.inner_text()).strip()
                    if text:
                        return text
            except Exception:
                continue
        return ""

    def _parse_date(self, date_str: str) -> str:
        """
        Convierte múltiples formatos de fecha a YYYY-MM-DD.
        Si no puede parsear, devuelve la fecha de hoy.
        """
        today = datetime.today()
        if not date_str:
            return today.strftime("%Y-%m-%d")

        # Formato ISO exacto
        m = re.search(r"(\d{4}-\d{2}-\d{2})", date_str)
        if m:
            return m.group(1)

        # Formato "hace X días/semanas/horas" en español o inglés
        date_str_lower = date_str.lower()
        m_days  = re.search(r"(\d+)\s*(day|día|dias|días)", date_str_lower)
        m_weeks = re.search(r"(\d+)\s*(week|semana)", date_str_lower)
        m_hours = re.search(r"(\d+)\s*(hour|hora)", date_str_lower)
        m_mins  = re.search(r"(\d+)\s*(min)", date_str_lower)

        if m_days:
            return (today - timedelta(days=int(m_days.group(1)))).strftime("%Y-%m-%d")
        if m_weeks:
            return (today - timedelta(weeks=int(m_weeks.group(1)))).strftime("%Y-%m-%d")
        if m_hours or m_mins:
            return today.strftime("%Y-%m-%d")

        # Intentar parseo libre
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%B %d, %Y", "%d de %B de %Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_str.split("T")[0], fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue

        return today.strftime("%Y-%m-%d")

    def _build_record(
        self,
        title: str,
        company: str,
        location: str,
        url: str,
        date_str: str,
    ) -> Dict[str, Any]:
        applied_date = self._parse_date(date_str)
        skills = self._infer_skills_from_title(title)
        return {
            "id": f"li-applied-{hash(url) & 0xffffff:06x}",
            "title": title.strip(),
            "company": (company or "Sin empresa").strip(),
            "location": (location or "No especificada").strip(),
            "url": url.strip(),
            "applied_date": applied_date,
            "status": "Postulado",
            "notes": "Importado desde LinkedIn Jobs Tracker",
            "description": f"Postulación a {title} en {company or 'empresa'}.",
            "skills": skills,
            "source": "linkedin_tracker",
        }

    def _infer_skills_from_title(self, title: str) -> List[str]:
        t = title.lower()
        skills = []
        if "python" in t:                             skills.append("Python")
        if "react" in t:                              skills.append("React")
        if "full stack" in t or "fullstack" in t:     skills.extend(["React", "Node.js"])
        if "backend" in t:                            skills.extend(["Python", "SQL"])
        if "frontend" in t:                           skills.extend(["JavaScript", "React"])
        if "data" in t:                               skills.extend(["Python", "SQL"])
        if "ai" in t or "machine learning" in t:      skills.extend(["Python", "Machine Learning"])
        if "java" in t and "javascript" not in t:     skills.append("Java")
        if "node" in t:                               skills.append("Node.js")
        if "devops" in t or "cloud" in t:             skills.extend(["Docker", "AWS"])
        if not skills:
            skills = ["Software Development", "Git"]
        return list(dict.fromkeys(skills))
