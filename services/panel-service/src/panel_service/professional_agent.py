"""
Professional Agent Module for Vadi-Pehn Career Exploration Panel.
Provides specialized professional guidance, career pathway analysis, skill mapping, and mentorship.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

logger = logging.getLogger("panel_service.professional_agent")


class ProfessionalAgent:
    """
    Professional Domain Mentor Agent.
    Helps youth discover career options, understand requisite skills, and design realistic milestones.
    """

    def __init__(self, agent_id: str = "agent-professional-career-v1") -> None:
        self.agent_id = agent_id
        self.system_prompt = (
            "You are a warm, encouraging, and highly knowledgeable Career & Skill Guide. "
            "Your role is to inspire youth (ages 8-17) by breaking down professional career pathways "
            "into fun, achievable learning steps and practical skill roadmaps."
        )

    async def generate_career_guidance(
        self,
        *,
        learner_id: UUID,
        interests: List[str],
        query: str,
    ) -> Dict[str, Any]:
        """
        Generates structured career exploration guidance and milestone suggestions.
        """
        logger.info(f"ProfessionalAgent generating guidance for learner {learner_id} with interests: {interests}")
        
        # Example structured breakdown
        suggested_careers = []
        for interest in interests:
            if "code" in interest.lower() or "tech" in interest.lower() or "math" in interest.lower():
                suggested_careers.append("Software Developer & AI Innovator")
            elif "art" in interest.lower() or "design" in interest.lower():
                suggested_careers.append("Digital Product & Game Designer")
            elif "science" in interest.lower() or "doctor" in interest.lower():
                suggested_careers.append("Biomedical Researcher")
        
        if not suggested_careers:
            suggested_careers.append("Technology Explorer & Problem Solver")

        response_text = (
            f"Based on your passion for {', '.join(interests)}, awesome career paths to explore include: "
            f"{', '.join(suggested_careers)}! "
            f"To get started, focus on building core skills like logic, problem-solving, and creative design."
        )

        return {
            "agent_name": "Professional Mentor",
            "agent_id": self.agent_id,
            "response": response_text,
            "suggested_careers": suggested_careers,
            "milestones": ["Try a beginner coding or design tutorial", "Build a simple project", "Share with family!"],
        }
