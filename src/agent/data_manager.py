import json
import os
from pathlib import Path
from typing import Dict, List, Any

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

PROFILE_PATH = DATA_DIR / "profile.json"
APPLIED_PATH = DATA_DIR / "applied.json"
JOBS_PATH = DATA_DIR / "jobs.json"

class DataManager:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    def load_profile(self) -> Dict[str, Any]:
        if not PROFILE_PATH.exists():
            return {
                "user_name": "Usuario",
                "target_roles": ["Software Engineer", "Backend Developer"],
                "skills": ["Python", "JavaScript", "SQL", "Git"],
                "preferred_locations": ["Chile", "Remote"],
                "search_keywords": ["Software Engineer"]
            }
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_profile(self, profile: Dict[str, Any]) -> None:
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)

    def load_applied_jobs(self) -> List[Dict[str, Any]]:
        if not APPLIED_PATH.exists():
            return []
        with open(APPLIED_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_applied_jobs(self, applied_jobs: List[Dict[str, Any]]) -> None:
        with open(APPLIED_PATH, "w", encoding="utf-8") as f:
            json.dump(applied_jobs, f, ensure_ascii=False, indent=2)

    def load_jobs(self) -> List[Dict[str, Any]]:
        if not JOBS_PATH.exists():
            return []
        with open(JOBS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_jobs(self, jobs: List[Dict[str, Any]]) -> None:
        with open(JOBS_PATH, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)

    def merge_discovered_jobs(self, new_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        existing_jobs = self.load_jobs()
        existing_urls = {j.get("url") for j in existing_jobs if j.get("url")}
        existing_ids = {j.get("id") for j in existing_jobs if j.get("id")}

        added_count = 0
        for job in new_jobs:
            url = job.get("url")
            job_id = job.get("id")
            if url and url in existing_urls:
                continue
            if job_id and job_id in existing_ids:
                continue
            existing_jobs.append(job)
            added_count += 1

        self.save_jobs(existing_jobs)
        print(f"[DataManager] Se agregaron {added_count} nuevos empleos a la base de datos.")
        return existing_jobs
