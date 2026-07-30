import re
from typing import List, Dict, Any, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class JobMatcher:
    def __init__(self, profile: Dict[str, Any], applied_jobs: List[Dict[str, Any]]):
        self.profile = profile
        self.applied_jobs = applied_jobs
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.learned_keywords = self._extract_learned_keywords()

    def _extract_learned_keywords(self) -> List[str]:
        """Extrae palabras clave y habilidades más frecuentes de empleos a los que se ha postulado."""
        words_count = {}
        for app in self.applied_jobs:
            text = f"{app.get('title', '')} {app.get('description', '')} {' '.join(app.get('skills', []))}"
            # Extraer palabras relevantes
            tokens = re.findall(r'\b[a-zA-ZáéíóúÁÉÍÓÚñÑ#+]{3,}\b', text.lower())
            for t in tokens:
                words_count[t] = words_count.get(t, 0) + 1

        # Ordenar por frecuencia
        sorted_words = sorted(words_count.items(), key=lambda x: x[1], reverse=True)
        return [w for w, c in sorted_words[:30]]

    def score_job(self, job: Dict[str, Any]) -> Tuple[int, List[str]]:
        """Calcula el Match Score (0-100%) y genera las razones del puntaje."""
        user_skills = [s.lower() for s in self.profile.get("skills", [])]
        target_roles = [r.lower() for r in self.profile.get("target_roles", [])]
        
        job_title = job.get("title", "").lower()
        job_desc = job.get("description", "").lower()
        job_skills = [s.lower() for s in job.get("skills", [])]
        job_text = f"{job_title} {job_desc} {' '.join(job_skills)}"

        reasons = []
        score = 0.0

        # 1. Coincidencia de habilidades (40% del score)
        found_skills = [s for s in user_skills if s in job_text]
        if user_skills:
            skill_ratio = len(found_skills) / len(user_skills)
            score += min(skill_ratio * 40.0, 40.0)
            if found_skills:
                reasons.append(f"Habilidades coincidentes: {', '.join([s.title() for s in found_skills[:4]])}")

        # 2. Coincidencia con roles objetivo (30% del score)
        role_match = any(role in job_title for role in target_roles)
        if role_match:
            score += 30.0
            reasons.append("El título coincide con tus roles preferidos")
        else:
            # Parcial match
            partial_role = any(role.split()[0] in job_title for role in target_roles if role)
            if partial_role:
                score += 15.0
                reasons.append("El título coincide parcialmente con tus roles de interés")

        # 3. Aprendizaje de postulaciones previas (TF-IDF & Learned Keywords) (30% del score)
        if self.applied_jobs:
            applied_texts = [
                f"{app.get('title', '')} {app.get('description', '')}" 
                for app in self.applied_jobs
            ]
            corpus = applied_texts + [job_text]
            try:
                tfidf_matrix = self.vectorizer.fit_transform(corpus)
                sim_matrix = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])
                max_sim = float(sim_matrix.max()) if sim_matrix.size > 0 else 0.0
                learned_score = min(max_sim * 30.0, 30.0)
                score += learned_score
                if max_sim > 0.2:
                    reasons.append(f"Similitud del {int(max_sim*100)}% con tus postulaciones previas")
            except Exception:
                pass

        # Bonus por remoto si está en preferencias
        if self.profile.get("remote_only") and "remot" in job_text:
            score += 5.0
            reasons.append("Modalidad Remota deseada")

        final_score = int(min(max(score, 10.0), 99.0))
        if not reasons:
            reasons.append("Cumple con criterios generales de búsqueda")

        return final_score, reasons

    def process_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Procesa una lista de empleos, calculando el score de match para cada uno."""
        processed = []
        for job in jobs:
            score, reasons = self.score_job(job)
            job_copy = dict(job)
            job_copy["match_score"] = score
            job_copy["match_reasons"] = reasons
            processed.append(job_copy)

        # Ordenar por match score descendente
        processed.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return processed
