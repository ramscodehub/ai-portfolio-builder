# backend/app/services/llm_service.py
import base64
import asyncio
import traceback
from fastapi import HTTPException

import google.cloud.aiplatform as aiplatform
from vertexai.generative_models import GenerativeModel, Part, Image
from vertexai.generative_models import GenerationConfig, SafetySetting, HarmCategory, HarmBlockThreshold
import google.api_core.exceptions

# Import config variables
from app.core import config

_vertex_ai_initialized = False

def initialize_vertex_ai():
    global _vertex_ai_initialized
    if _vertex_ai_initialized: return True
    if not config.GCP_PROJECT_ID:
        print("CRITICAL: GCP_PROJECT_ID is not defined. LLM functionality will be unavailable.")
        _vertex_ai_initialized = False
        return False
    try:
        print(f"Attempting to initialize Vertex AI for project {config.GCP_PROJECT_ID} in {config.GCP_LOCATION}...")
        aiplatform.init(project=config.GCP_PROJECT_ID, location=config.GCP_LOCATION)
        print(f"Vertex AI successfully initialized for project {config.GCP_PROJECT_ID} in {config.GCP_LOCATION}.")
        _vertex_ai_initialized = True
        return True
    except Exception as e:
        print(f"CRITICAL: Error initializing Vertex AI: {e}\n{traceback.format_exc()}")
        _vertex_ai_initialized = False
        return False

async def generate_html_with_llm(cleaned_html: str, desktop_screenshot_base64: str, mobile_screenshot_base64: str) -> str:
    if not initialize_vertex_ai():
        raise HTTPException(status_code=500, detail="Vertex AI not initialized or initialization failed.")
    
    system_prompt = """
You are an expert web developer specializing in creating HTML and CSS replicas of websites.
Your goal is to generate a single, self-contained HTML file with an embedded CSS <style> block in the <head> that visually replicates the provided website design as closely as possible.
You will be given:
1. A desktop screenshot of the target website (as base64 encoded PNG).
2. A mobile screenshot of the target website (as base64 encoded PNG).
3. A cleaned HTML structure of the target website's body content. This HTML has had most classes, styles, and data attributes removed. Focus on the semantic tags and the visual information from the screenshots to determine styling and layout.
Instructions:
- Analyze the screenshots for layout, typography (font families, sizes, weights, colors), colors, spacing, borders, shadows, and other visual elements for both desktop and mobile views.
- Use the provided cleaned HTML as a structural guide. Recreate the elements present in this HTML.
- Generate appropriate CSS within a single `<style>` block in the `<head>` of the HTML document to match the visual appearance in the screenshots.
- Use media queries (e.g., @media (max-width: 768px) { ... }) for responsiveness to ensure the design adapts between the desktop and mobile screenshot appearances.
- Pay attention to the semantic meaning of HTML tags (e.g., <nav>, <button>, <h1>) when deciding on styles.
- If you see empty <div> tags in the provided HTML where an icon might have been (based on the screenshot), you can either omit the div or, if an icon is clearly visible and simple (like an arrow or a common symbol), you can try to replicate it using a simple inline SVG or a Unicode character. For complex icons or logos not provided as images, use a placeholder description like <!-- placeholder for search icon --> or omit.
- Ensure the generated HTML is well-formed, including <!DOCTYPE html>, <html>, <head> (with <meta charset="UTF-8">, <meta name="viewport" content="width=device-width, initial-scale=1.0">, and <title>Website Clone</title>), and <body> tags.
- Prioritize visual similarity to the screenshots.
- Do not use any external CSS libraries or JavaScript. The output should be a single HTML file.
- For fonts, try to use common web-safe fonts (e.g., Arial, Helvetica, sans-serif; Times New Roman, serif; Courier New, monospace) that approximate the look in the screenshots. If a very specific font name is obvious (like "Uber Move Display"), you can specify it in the CSS `font-family` property.
- For images visible in the screenshot but not represented by <img> tags in the cleaned HTML (e.g., background images), you should try to include them using CSS background-image properties. Use descriptive placeholder URLs like "placeholder-background-image.jpg" or similar if the actual image source isn't available.
- The final output should be ONLY the complete HTML code, starting with <!DOCTYPE html>. Do not include any conversational text or explanations before or after the HTML code block.
    """
    max_retries = 2; base_delay = 5
    current_max_output_tokens = 65000 # Using the model's known limit

    for attempt in range(max_retries + 1):
        try:
            model = GenerativeModel(config.MODEL_NAME)
            prompt_parts = [
                Part.from_text(system_prompt), Part.from_text("\n\nHere is the design context:\n\nCleaned HTML Structure:\n```html\n"),
                Part.from_text(cleaned_html), Part.from_text("\n```\n\nDesktop Screenshot (Base64 PNG):\n"),
                Part.from_image(Image.from_bytes(base64.b64decode(desktop_screenshot_base64))),
                Part.from_text("\n\nMobile Screenshot (Base64 PNG):\n"),
                Part.from_image(Image.from_bytes(base64.b64decode(mobile_screenshot_base64))),
                Part.from_text("\n\nPlease generate the complete HTML code as a single block, starting with <!DOCTYPE html>.")
            ]
            generation_config_obj = GenerationConfig(temperature=0.2, top_p=0.95, top_k=40, max_output_tokens=current_max_output_tokens, response_mime_type="text/plain")
            safety_settings_list = [
                SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE)
            ]
            
            print(f"Sending request to Gemini model (Attempt {attempt + 1}): {config.MODEL_NAME} with max_output_tokens={current_max_output_tokens}...")
            response = await model.generate_content_async(contents=prompt_parts, generation_config=generation_config_obj, safety_settings=safety_settings_list)
            print("Received response from Gemini.")
            
            if response and response.candidates:
                candidate = response.candidates[0]
                print(f"Candidate Finish Reason: {candidate.finish_reason}")
                if hasattr(candidate, 'safety_ratings'): print(f"Candidate Safety Ratings: {candidate.safety_ratings}")
                if hasattr(response, 'usage_metadata'): print(f"Usage Metadata: {response.usage_metadata}")
                
                if candidate.finish_reason == 2: print("Warning: Output truncated due to MAX_TOKENS limit.")
                
                if candidate.content and candidate.content.parts:
                    raw_generated_text = "".join(p.text for p in candidate.content.parts if hasattr(p, 'text') and p.text)
                    print(f"RAW LLM OUTPUT (first 500 chars):\n---\n{raw_generated_text[:500]}...\n---")
                    
                    generated_html = raw_generated_text
                    if generated_html.strip().startswith("```html"): generated_html = generated_html.strip()[7:]
                    if generated_html.strip().endswith("```"): generated_html = generated_html.strip()[:-3]
                    
                    if not generated_html.strip() and candidate.finish_reason == 1: 
                         print("Warning: Generated HTML is empty after stripping markdown, though model stopped naturally.")
                    return generated_html.strip() 
            raise HTTPException(status_code=500, detail="LLM response did not contain valid candidates or content.")
        
        except google.api_core.exceptions.ResourceExhausted as e_res_exhausted:
            print(f"ResourceExhausted error (Attempt {attempt + 1}): {e_res_exhausted}")
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                print("Max retries reached for ResourceExhausted error.")
                raise HTTPException(status_code=429, detail=f"Resource exhausted after multiple retries: {str(e_res_exhausted)}")
        except Exception as e:
            print(f"Error calling LLM: {type(e).__name__} - {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to generate HTML with LLM. Error: {str(e)}")
    
    raise HTTPException(status_code=500, detail="LLM generation failed after all attempts.")