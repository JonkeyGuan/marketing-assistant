"""
Skill: Generate Campaign HTML

Uses an LLM (via OpenAI-compatible API) to generate luxury marketing landing pages.
"""
from typing import Dict


CODER_SYSTEM_PROMPT = """You are an expert frontend developer specializing in luxury marketing landing pages for high-end casinos in Macau.

Your task is to generate a complete, responsive, single-page HTML file with embedded CSS and JavaScript for a marketing campaign.

## Requirements:
1. Create a visually stunning, mobile-responsive landing page
2. Use the provided color scheme consistently throughout
3. Include smooth animations and hover effects
4. Add a clear call-to-action button
5. Include the casino/hotel branding
6. Make it feel luxurious and exclusive

## Technical Requirements:
- Single HTML file with embedded <style> and <script> tags
- Use modern CSS (flexbox, grid, CSS variables)
- No external dependencies (no CDN links)
- Responsive design (mobile-first)
- Smooth scroll behavior
- Subtle animations (fade-ins, hover effects)

## Page Sections to Include:
1. Hero section with campaign headline and gradient/animated background
2. Campaign details section explaining the offer
3. Benefits/features section with visual elements
4. Call-to-action section with a prominent button
5. Footer with hotel branding

## Output Format:
Return ONLY the complete HTML code, starting with <!DOCTYPE html> and ending with </html>.
Do not include any explanations or markdown code blocks - just the raw HTML.
"""


def generate_campaign_html(
    campaign_name: str,
    campaign_description: str,
    hotel_name: str,
    theme_colors: Dict[str, str],
    theme_name: str,
    start_date: str = "",
    end_date: str = "",
) -> str:
    """Generate HTML content for the campaign using the LLM with streaming."""
    from app.settings import settings
    import httpx
    import json

    date_info = ""
    if start_date and end_date:
        date_info = f"\n- **Campaign Period:** {start_date} to {end_date}"
    elif end_date:
        date_info = f"\n- **Offer Expires:** {end_date}"

    user_prompt = f"""Create a marketing landing page with the following details:

## Campaign Information:
- **Campaign Name:** {campaign_name}
- **Description:** {campaign_description}
- **Hotel/Casino:** {hotel_name}
- **Theme:** {theme_name}{date_info}

## Color Scheme:
- Primary Color: {theme_colors.get('primary', '#D4AF37')}
- Secondary Color: {theme_colors.get('secondary', '#1A1A1A')}
- Accent Color: {theme_colors.get('accent', '#FFFFFF')}
- Background Color: {theme_colors.get('background', '#0D0D0D')}
- Text Color: {theme_colors.get('text', '#FFFFFF')}

## Page Sections to Include:
1. Hero section with campaign headline and a stunning gradient background
2. Campaign details section explaining the offer with elegant typography
3. Display the campaign dates prominently: {start_date} to {end_date}
4. Benefits/features section (use icons or visual elements)
5. Call-to-action section with a prominent, animated button
6. Footer with hotel branding and contact info

Make it visually impressive with CSS animations, gradients, and a luxury feel.
IMPORTANT: Use the actual dates provided ({start_date} to {end_date}), NOT placeholders.

Generate the complete HTML file now:"""

    url = f"{settings.MODEL_ENDPOINT}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.MODEL_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "model": settings.MODEL_NAME,
        "messages": [
            {"role": "system", "content": CODER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 8000,
        "temperature": 0.7,
        "stream": True,
    }

    html_content = ""
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
                                html_content += content
                    except json.JSONDecodeError:
                        continue

    # Clean up the response - remove markdown code blocks if present
    if html_content.startswith("```"):
        lines = html_content.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        html_content = "\n".join(lines)

    return html_content
