import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)

class SEOAnalyzer:
    @staticmethod
    def analyze(html_content):
        """Analyzes HTML payload for SEO best practices using Gemini."""
        if not api_key:
            return {
                "score": 0,
                "suggestions": ["GEMINI_API_KEY is missing. Cannot perform AI SEO analysis."]
            }
            
        try:
            model = genai.GenerativeModel('models/gemini-2.5-flash')
            prompt = f"""
            You are an expert SEO analyzer. Analyze this HTML snippet.
            Review for:
            - Missing or empty meta tags (title, description).
            - Missing alt attributes on standard <img> tags or font-awesome elements without aria-labels.
            - Heading hierarchy (H1, H2, etc).
            - Semantic structure.

            Return EXACTLY a JSON dictionary like this:
            {{
                "score": 85,
                "suggestions": [
                    "Add an alt attribute to the second image.",
                    "Ensure there is only one H1 tag."
                ]
            }}

            HTML CONTENT:
            ```html
            {html_content}
            ```
            """
            
            response = model.generate_content(prompt, generation_config={"temperature": 0.2})
            
            # Clean JSON
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
                
            data = json.loads(text.strip())
            return {
                "score": data.get("score", 0),
                "suggestions": data.get("suggestions", [])
            }
        except Exception as e:
            return {
                "score": 0,
                "suggestions": [f"Analysis failed: {str(e)}"]
            }
