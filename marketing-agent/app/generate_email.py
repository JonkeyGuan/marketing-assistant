"""
Core skill: Generate marketing email content in English and Chinese.

Uses an LLM (via OpenAI-compatible API) to generate bilingual marketing emails.
"""
import json
import logging
from typing import Dict

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)

MARKETING_SYSTEM_PROMPT = """You are a luxury marketing copywriter for high-end Macau casinos.

Your task is to write compelling, personalized marketing email content that:
- Appeals to high-net-worth individuals
- Maintains brand elegance and exclusivity
- Uses sophisticated, refined language
- Includes clear calls-to-action
- Creates a sense of urgency and exclusivity

## Output Format:
You MUST provide content in BOTH English and Chinese (Simplified).

Structure your response EXACTLY as follows:

---ENGLISH_SUBJECT---
[English email subject line here]

---ENGLISH_BODY---
[English email body as HTML fragment - see formatting rules below]

---CHINESE_SUBJECT---
[Chinese email subject line here]

---CHINESE_BODY---
[Chinese email body as HTML fragment - see formatting rules below]

## Email Body HTML Formatting Rules:
- Use ONLY inline HTML tags like <h1>, <h2>, <p>, <strong>, <em>, <a>, <br>
- Do NOT include <!DOCTYPE>, <html>, <head>, <body>, or <style> tags
- Do NOT wrap content in any document structure
- For the CTA button, use: <a href="URL" style="background-color:#C41E3A;color:#ffffff;padding:12px 24px;text-decoration:none;border-radius:5px;display:inline-block;font-weight:bold;">Button Text</a>

## Email Style Guidelines:
- Keep subject lines under 60 characters
- Use elegant, premium language
- Include personalization placeholder {{customer_name}} for the greeting
- Add a prominent call-to-action button that links to the ACTUAL campaign URL provided (NOT a placeholder)
- Sign off with the hotel/casino name

IMPORTANT: The call-to-action button href MUST use the exact campaign URL provided in the prompt. Do NOT use placeholder text like "{{campaign_url}}" - use the actual URL.
"""


def _parse_email_response(response: str) -> Dict[str, str]:
    """Parse the structured email response into components."""
    result = {
        "subject_en": "",
        "body_en": "",
        "subject_zh": "",
        "body_zh": "",
    }

    if "---ENGLISH_SUBJECT---" in response:
        start = response.find("---ENGLISH_SUBJECT---") + len("---ENGLISH_SUBJECT---")
        end = response.find("---ENGLISH_BODY---") if "---ENGLISH_BODY---" in response else len(response)
        result["subject_en"] = response[start:end].strip()

    if "---ENGLISH_BODY---" in response:
        start = response.find("---ENGLISH_BODY---") + len("---ENGLISH_BODY---")
        end = response.find("---CHINESE_SUBJECT---") if "---CHINESE_SUBJECT---" in response else len(response)
        result["body_en"] = response[start:end].strip()

    if "---CHINESE_SUBJECT---" in response:
        start = response.find("---CHINESE_SUBJECT---") + len("---CHINESE_SUBJECT---")
        end = response.find("---CHINESE_BODY---") if "---CHINESE_BODY---" in response else len(response)
        result["subject_zh"] = response[start:end].strip()

    if "---CHINESE_BODY---" in response:
        start = response.find("---CHINESE_BODY---") + len("---CHINESE_BODY---")
        result["body_zh"] = response[start:].strip()

    return result


def generate_email_content(
    campaign_name: str,
    campaign_description: str,
    hotel_name: str,
    campaign_url: str,
    target_audience: str,
    start_date: str = "",
    end_date: str = "",
) -> Dict[str, str]:
    """Generate bilingual email content using the LLM with streaming."""
    date_info = ""
    if start_date and end_date:
        date_info = f"\n- **Campaign Period:** {start_date} to {end_date}"
    elif end_date:
        date_info = f"\n- **Offer Expires:** {end_date}"

    user_prompt = f"""Create a marketing email for the following campaign:

## Campaign Details:
- **Campaign Name:** {campaign_name}
- **Description:** {campaign_description}
- **Hotel/Casino:** {hotel_name}
- **Campaign Landing Page URL:** {campaign_url}
- **Target Audience:** {target_audience}{date_info}

## Requirements:
1. Create an enticing subject line that drives opens
2. Write an elegant email body with:
   - Personalized greeting using {{{{customer_name}}}} placeholder
   - Compelling description of the offer
   - Include the campaign dates ({start_date} to {end_date}) in the email body
   - Sense of exclusivity and urgency
   - A styled call-to-action button with href="{campaign_url}" (use this EXACT URL)
   - Professional sign-off from {hotel_name}
3. Use HTML formatting for the body (headers, paragraphs, button styling)
4. Provide both English and Chinese versions

CRITICAL:
- The CTA button MUST link to: {campaign_url}
- Use the ACTUAL dates provided ({start_date} to {end_date}), NOT placeholders like [date]

Generate the email content now:"""

    url = f"{settings.MODEL_ENDPOINT}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.MODEL_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "model": settings.MODEL_NAME,
        "messages": [
            {"role": "system", "content": MARKETING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 4000,
        "temperature": 0.7,
        "stream": True,
    }

    response_content = ""
    with httpx.Client(timeout=300.0) as client:
        with client.stream("POST", url, json=data, headers=headers) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    json_str = line[6:]
                    if json_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(json_str)
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                response_content += content
                    except json.JSONDecodeError:
                        continue

    return _parse_email_response(response_content)
