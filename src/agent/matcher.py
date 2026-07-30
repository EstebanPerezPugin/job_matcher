import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class JobMatcher:
    def __init__(self, profile: Dict[str, Any], applied_jobs: List[Dict[str, Any]]):
        self.profile = profile
        self.all_applied = applied_jobs
        self.recent_applied = self._filter_recent_applied(months=profile.get("timeframe_months", 6))
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.learned_keywords = self._extract_learned_keywords()

    def _filter_recent_applied(self, months: int = 6) -> List[Dict[str, Any]]:
        """Filtra únicamente las postulaciones realizadas en los últimos N meses."""
        cutoff_date = datetime.now() - timedelta(days=months * 30)
        recent = []
        for app in self.all_applied:
            date_str = app.get("applied_date", "")
            try:
                app_date = datetime.strptime(date_str, "%Y-%m-%d")
                if app_date >= cutoff_date:
                    recent.append(app)
            except ValueError:
                # Si no tiene fecha válida, asumir que es reciente
                recent.append(app)
        return recent

    def _extract_learned_keywords(self) -> List[str]:
        """Extrae palabras clave y habilidades de empleos postulados en los últimos 6 meses."""
        words_count = {}
        target_dataset = self.recent_applied if self.recent_applied else self.all_applied
        
        for app in target_dataset:
            text = f"{app.get('title', '')} {app.get('description', '')} {' '.join(app.get('skills', []))}"
            tokens = re.findall(r'\b[a-zA-ZáéíóúÁÉÍÓÚñÑ#+]{3,}\b', text.lower())
            for t in tokens:
                words_count[t] = words_count.get(t, 0) + 1

        sorted_words = sorted(words_count.items(), key=lambda x: x[1], reverse=True)
        return [w for w, c in sorted_words[:35]]

    def score_job(self, job: Dict[str, Any]) -> Tuple[int, List[str]]:
        """Calcula el Match Score (0-100%) y genera las razones del puntaje priorizando postulaciones recientes."""
        user_skills = [s.lower() for s in self.profile.get("skills", [])]
        target_roles = [r.lower() for r in self.profile.get("target_roles", [])]
        linkedin_headline = self.profile.get("linkedin_headline", "").lower()
        
        job_title = job.get("title", "").lower()
        job_desc = job.get("description", "").lower()
        job_skills = [s.lower() for s in job.get("skills", [])]
        job_text = f"{job_title} {job_desc} {' '.join(job_skills)}"

        reasons = []
        score = 0.0

        # 1. Coincidencia con titular de Perfil de LinkedIn & Habilidades (35%)
        found_skills = [s for s in user_skills if s in job_text]
        if user_skills:
            skill_ratio = len(found_skills) / len(user_skills)
            score += min(skill_ratio * 35.0, 35.0)
            if found_skills:
                reasons.append(f"Habilidades coincidentes: {', '.join([s.title() for s in found_skills[:4]])}")

        # Coincidencia con Titular de LinkedIn
        if linkedin_headline and any(part in job_text for part in linkedin_headline.split("|")):
            score += 10.0
            reasons.append("Alineado con tu Titular de LinkedIn")

        # 2. Coincidencia con Roles Objetivo (25%)
        role_match = any(role in job_title for role in target_roles)
        if role_match:
            score += 25.0
            reasons.append("Título en tus roles preferidos")
        else:
            partial_role = any(role.split()[0] in job_title for role in target_roles if role)
            if partial_role:
                score += 12.0

        # 3. Aprendizaje de postulaciones de los ÚLTIMOS 6 MESES (30%)
        target_apps = self.recent_applied if self.recent_applied else self.all_applied
        if target_apps:
            applied_texts = [
                f"{app.get('title', '')} {app.get('description', '')}" 
                for app in target_apps
            ]
            corpus = applied_texts + [job_text]
            try:
                tfidf_matrix = self.vectorizer.fit_transform(corpus)
                sim_matrix = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])
                max_sim = float(sim_matrix.max()) if sim_matrix.size > 0 else 0.0
                learned_score = min(max_sim * 30.0, 30.0)
                score += learned_score
                if max_sim > 0.2:
                    reasons.append(f"Similitud del {int(max_sim*100)}% con tus postulaciones de los últimos 6 meses")
            except Exception:
                pass

        # Bonus por modalidad remota si corresponde
        if self.profile.get("remote_only") and "remot" in job_text:
            score += 5.0

        final_score = int(min(max(score, 10.0), 99.0))
        if not reasons:
            reasons.append("Coincide con criterios de búsqueda")

        return final_score, reasons

    def process_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Procesa una lista de empleos, calculando el score de match para cada uno."""
        processed = []
        for job in jobs:
            score, reasons = self.score_job(job)
            job_copy = dict(job)
            job_copy["match_score"] = score
            job_copy["match_reasons"] = reasons
            job_copy["is_recent_match"] = any("últimos 6 meses" in r for r in reasons)
            processed.append(job_copy)

        processed.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return processed
