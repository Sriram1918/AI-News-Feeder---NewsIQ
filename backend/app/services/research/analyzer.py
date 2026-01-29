"""
Deep Research Analyzer Service

Generates context analysis using Google Gemini.
Following official Google Generative AI Python SDK documentation:
https://github.com/google-gemini/generative-ai-python
"""

import asyncio
from datetime import datetime
from typing import List, Optional

import google.generativeai as genai

from app.config.logging import get_logger
from app.config.settings import settings
from app.models import Article

logger = get_logger(__name__)


# System prompt for Deep Research analysis
ANALYSIS_SYSTEM_PROMPT = """You are a news analysis assistant helping users understand complex events with nuance and accuracy.

Your task: Analyze the provided article and related sources to generate a 200-word context report.

Required sections:
1. **Background** (40 words): What led to this event? Essential historical context.
2. **Key Players** (30 words): Who's involved and what are their positions/interests?
3. **Perspectives** (60 words): What are the main arguments? Include at least one opposing viewpoint.
4. **Verification** (40 words): What facts are confirmed? What's disputed or unverified?
5. **What's Next** (30 words): Likely developments or things to watch.

Constraints:
- Total length: EXACTLY 200 words (±10 words acceptable)
- Cite sources using [Source Name] format
- Use neutral, journalistic tone
- Acknowledge uncertainty where appropriate
- If conflicting information exists, explicitly note disagreement
- No speculation beyond reasonable extrapolation

Format: Use markdown with bold section headers. Include clickable source citations."""


class Analyzer:
    """
    Deep Research Analyzer using Google Gemini.
    
    Features:
    - Structured context analysis
    - Source citation
    - Prompt engineering for consistent output
    """
    
    def __init__(self):
        """Initialize the analyzer."""
        genai.configure(api_key=settings.google_api_key)
        self.model_name = settings.gemini_model
        self.max_tokens = settings.gemini_max_tokens
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=ANALYSIS_SYSTEM_PROMPT,
        )
        
        logger.info("Initialized Analyzer", model=self.model_name)
    
    def _build_user_prompt(
        self,
        article: Article,
        related_articles: List[Article],
    ) -> str:
        """
        Build the user prompt for analysis.
        
        Args:
            article: Main article to analyze.
            related_articles: Related sources for context.
            
        Returns:
            Formatted user prompt.
        """
        # Main article section
        prompt = f"""MAIN ARTICLE:
Title: {article.title}
Source: {article.source}
Date: {article.published_at.strftime('%Y-%m-%d') if article.published_at else 'Unknown'}
Content: {article.content[:3000]}

RELATED SOURCES:
"""
        
        # Add related articles
        for idx, related in enumerate(related_articles, 1):
            # Extract key excerpt (first 500 chars of content)
            excerpt = related.content[:500] if related.content else ""
            if len(related.content) > 500:
                # Try to end at a sentence
                last_period = excerpt.rfind(".")
                if last_period > 300:
                    excerpt = excerpt[:last_period + 1]
            
            prompt += f"""
---
Source {idx}: [{related.source}]
Title: {related.title}
Date: {related.published_at.strftime('%Y-%m-%d') if related.published_at else 'Unknown'}
Key Excerpt: {excerpt}
URL: {related.url}
"""
        
        prompt += """
Generate the 200-word context report following the format specified in your instructions."""
        
        return prompt
    
    async def analyze(
        self,
        article: Article,
        related_articles: List[Article],
    ) -> str:
        """
        Generate context analysis for an article.
        
        Args:
            article: Main article to analyze.
            related_articles: Related sources for context.
            
        Returns:
            Markdown-formatted analysis.
        """
        user_prompt = self._build_user_prompt(article, related_articles)
        
        try:
            # Run sync API in thread pool for async compatibility
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content(
                    user_prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=self.max_tokens,
                    ),
                )
            )
            
            # Extract response text
            analysis = response.text
            
            # Get token counts if available
            input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0) if hasattr(response, 'usage_metadata') else 0
            output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0) if hasattr(response, 'usage_metadata') else 0
            
            logger.info(
                "Generated analysis",
                article_id=str(article.id),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            
            return analysis
            
        except Exception as e:
            logger.error(
                "Analysis generation failed",
                article_id=str(article.id),
                error=str(e),
            )
            raise
    
    async def analyze_with_fallback(     
        self,
        article: Article,
        related_articles: List[Article],
    ) -> str:
        """
        Generate analysis with fallback for failures.
        
        Args:
            article: Main article to analyze.
            related_articles: Related sources for context.
            
        Returns:
            Markdown-formatted analysis or fallback message.
        """
        try:
            return await self.analyze(article, related_articles)
        except Exception as e:
            logger.error("Analysis failed, returning fallback", error=str(e))
            
            # Generate fallback response
            sources_list = ", ".join([f"[{a.source}]" for a in related_articles[:3]])
            
            return f"""**Analysis temporarily unavailable**

We found {len(related_articles)} related articles from sources including {sources_list or 'various outlets'}.

**Quick Summary:**
This article from {article.source} discusses: {article.title}

**Related Coverage:**
{"".join([f"- [{a.title[:60]}...]({a.url}) - {a.source}" + chr(10) for a in related_articles[:3]])}

*Full AI analysis is temporarily unavailable. Please try again later.*
"""


# Singleton instance
analyzer = Analyzer()
