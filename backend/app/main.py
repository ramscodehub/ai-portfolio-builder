import os
import base64
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn
from playwright.async_api import async_playwright
from fastapi.responses import FileResponse, HTMLResponse
from playwright_stealth import stealth_async
import asyncio
import traceback
from datetime import datetime

from bs4 import BeautifulSoup, Comment

import google.cloud.aiplatform as aiplatform
from vertexai.generative_models import GenerativeModel, Part, Image
from vertexai.generative_models import GenerationConfig, SafetySetting, HarmCategory, HarmBlockThreshold
import google.api_core.exceptions # <<< --- ADDED THIS IMPORT

# Hardcoded GCP Configuration
GCP_PROJECT_ID = "orchids-461923"
GCP_LOCATION = "global"
MODEL_NAME = "gemini-2.5-pro-preview-05-06"


GENERATED_HTML_DIR_NAME = "generated_html_clones"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_HTML_DIR_PATH = os.path.join(BASE_DIR, GENERATED_HTML_DIR_NAME)
os.makedirs(GENERATED_HTML_DIR_PATH, exist_ok=True)
STATIC_CLONES_PATH_PREFIX = "/clones"

app = FastAPI(title="Website Cloner API", version="0.3.1") # Version bump
app.mount(STATIC_CLONES_PATH_PREFIX, StaticFiles(directory=GENERATED_HTML_DIR_PATH), name="cloned_files")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:8000", "http://127.0.0.1:5500"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Pydantic Models (keep as before) ---
class UrlRequest(BaseModel): url: str = Field(..., example="https://www.example.com")
class ScrapedContext(BaseModel): desktop_screenshot_base64: str; mobile_screenshot_base64: str; simplified_html: str | None
class ScrapedContextResponse(BaseModel): desktop_screenshot_base64: str; mobile_screenshot_base64: str; simplified_html: str | None; original_url: str
class ClonedHtmlFileResponse(BaseModel): message: str; file_path: str; view_link: str | None = None
class GalleryItem(BaseModel): id: str; filename: str; view_link: str; category: str; title: str; description: str | None = None
class GalleryResponse(BaseModel): items: list[GalleryItem]

# --- HTML Cleaning Function (keep as before) ---
def clean_html_for_llm(html_content: str) -> str:
    if not html_content: return "<!-- HTML content was empty or not provided to cleaner -->"
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        tags_to_remove = ["script", "style", "noscript", "meta", "link", "svg"]
        for tag_name in tags_to_remove:
            for t in soup.find_all(tag_name): t.decompose()
        for comment_tag in soup.find_all(string=lambda text: isinstance(text, Comment)): comment_tag.extract()
        for picture_tag in soup.find_all('picture'):
            img_tag = picture_tag.find('img')
            if img_tag:
                source_to_use = None; sources = picture_tag.find_all('source')
                for s in sources:
                    if s.has_attr('srcset'):
                        first_src_in_srcset = s['srcset'].split(',')[0].strip().split(' ')[0]
                        if s.has_attr('type') and 'webp' in s['type']: source_to_use = first_src_in_srcset; break
                        elif not source_to_use: source_to_use = first_src_in_srcset
                if source_to_use: img_tag['src'] = source_to_use
                img_attrs_to_keep = ['src', 'alt']; current_img_attrs = dict(img_tag.attrs)
                for attr_name in current_img_attrs:
                    if attr_name not in img_attrs_to_keep: del img_tag[attr_name]
                picture_tag.replace_with(img_tag)
            else: picture_tag.decompose()
        allowed_attributes = {"a": ["href", "id", "aria-label", "role", "target"], "img": ["src", "alt", "id", "width", "height"], "input": ["type", "id", "name", "value", "placeholder", "aria-label", "checked", "disabled", "readonly"], "button": ["type", "id", "aria-label", "disabled"], "form": ["id", "action", "method"], "label": ["for", "id"], "textarea": ["id", "name", "placeholder", "aria-label", "rows", "cols", "readonly", "disabled"], "select": ["id", "name", "aria-label", "disabled", "multiple"], "option": ["value", "selected", "disabled", "label"], "iframe": ["src", "id", "title", "width", "height", "allowfullscreen", "frameborder"], "*": ["id", "aria-label", "aria-labelledby", "aria-describedby", "role", "lang", "title"]}
        for tag in soup.find_all(True):
            if tag.name in tags_to_remove: tag.decompose(); continue
            if 'class' in tag.attrs: del tag['class']
            if 'style' in tag.attrs: del tag['style']
            current_attrs = dict(tag.attrs); specific_allowed = allowed_attributes.get(tag.name, []); general_allowed = allowed_attributes.get("*", []); final_allowed_attrs = set(specific_allowed + general_allowed)
            for attr_name in current_attrs:
                if attr_name.startswith("data-") or attr_name not in final_allowed_attrs: del tag[attr_name]
                elif current_attrs[attr_name] == "" and attr_name not in ['alt', 'value', 'placeholder', 'src', 'href', 'action', 'for', 'id', 'name', 'title']: del tag[attr_name]
        if soup.body: return soup.body.prettify()
        return soup.prettify()
    except Exception as e: print(f"Error during HTML cleaning: {e}\n{traceback.format_exc()}"); return f"<!-- HTML cleaning process failed: {str(e)} -->"

# --- Website Scraping Function (keep as before) ---
async def scrape_website_context(url: str, retries: int = 1) -> ScrapedContext:
    last_exception = None; browser = None
    for attempt in range(retries + 1):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-accelerated-2d-canvas', '--no-first-run', '--no-zygote', '--disable-gpu'])
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36", extra_http_headers={"Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate, br", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"}, locale="en-US", viewport={"width": 1920, "height": 1080})
                page = await context.new_page(); await stealth_async(page)
                print(f"Attempt {attempt + 1}: Navigating to {url}..."); await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print(f"Waiting for page to settle (5s)..."); await page.wait_for_timeout(5000)
                print("Taking desktop screenshot..."); await page.set_viewport_size({"width": 1920, "height": 1080}); await page.wait_for_timeout(1500); desktop_buffer = await page.screenshot(full_page=True, timeout=30000)
                print("Taking mobile screenshot..."); await page.set_viewport_size({"width": 390, "height": 844}); await page.wait_for_timeout(1500); mobile_buffer = await page.screenshot(full_page=True, timeout=30000)
                desktop_base64 = base64.b64encode(desktop_buffer).decode('utf-8'); mobile_base64 = base64.b64encode(mobile_buffer).decode('utf-8')
                print("Extracting and cleaning HTML content..."); simplified_html_output: str | None
                try:
                    html_content_raw = await page.locator('body').inner_html(timeout=20000)
                    if html_content_raw: simplified_html_output = clean_html_for_llm(html_content_raw)
                    else: simplified_html_output = "<!-- Raw HTML content from page was empty -->"
                except Exception as html_e: print(f"Could not extract or clean HTML: {type(html_e).__name__} - {html_e}\n{traceback.format_exc()}"); simplified_html_output = f"<!-- HTML extraction/cleaning process failed: {str(html_e)} -->"
                await browser.close(); browser = None
                return ScrapedContext(desktop_screenshot_base64=desktop_base64, mobile_screenshot_base64=mobile_base64, simplified_html=simplified_html_output)
        except Exception as e:
            print(f"Error during scraping attempt {attempt + 1} for {url}: {type(e).__name__} - {e}\n{traceback.format_exc()}"); last_exception = e
            if browser and browser.is_connected(): await browser.close(); browser = None
            if attempt < retries: await asyncio.sleep(3 + attempt * 2)
            else: raise HTTPException(status_code=500, detail=f"Failed to scrape {url} after {retries + 1} attempts. Last error: {str(last_exception)}")
    raise HTTPException(status_code=500, detail=f"Scraping failed for {url} unexpectedly. Last error: {str(last_exception if last_exception else 'Unknown')}")

# --- LLM Interaction Function (Corrected) ---
_vertex_ai_initialized = False
def initialize_vertex_ai():
    global _vertex_ai_initialized
    if _vertex_ai_initialized: return True
    if not GCP_PROJECT_ID: print("CRITICAL: GCP_PROJECT_ID is not defined. LLM functionality will be unavailable."); _vertex_ai_initialized = False; return False
    try:
        print(f"Attempting to initialize Vertex AI for project {GCP_PROJECT_ID} in {GCP_LOCATION}..."); aiplatform.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
        print(f"Vertex AI successfully initialized for project {GCP_PROJECT_ID} in {GCP_LOCATION}."); _vertex_ai_initialized = True; return True
    except Exception as e: print(f"CRITICAL: Error initializing Vertex AI: {e}\n{traceback.format_exc()}"); _vertex_ai_initialized = False; return False

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
    max_retries = 2 
    base_delay = 5  
    
    current_max_output_tokens = 65000 # Using the model's known limit

    for attempt in range(max_retries + 1):
        try:
            model = GenerativeModel(MODEL_NAME) 
            prompt_parts = [
                Part.from_text(system_prompt), Part.from_text("\n\nHere is the design context:\n\nCleaned HTML Structure:\n```html\n"),
                Part.from_text(cleaned_html), Part.from_text("\n```\n\nDesktop Screenshot (Base64 PNG):\n"),
                Part.from_image(Image.from_bytes(base64.b64decode(desktop_screenshot_base64))),
                Part.from_text("\n\nMobile Screenshot (Base64 PNG):\n"),
                Part.from_image(Image.from_bytes(base64.b64decode(mobile_screenshot_base64))),
                Part.from_text("\n\nPlease generate the complete HTML code as a single block, starting with <!DOCTYPE html>.")
            ]
            generation_config_obj = GenerationConfig(
                temperature=0.2, 
                top_p=0.95, 
                top_k=40, 
                max_output_tokens=current_max_output_tokens, # Correctly using the variable
                response_mime_type="text/plain"
            )
            safety_settings_list = [
                SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE)
            ]
            
            print(f"Sending request to Gemini model (Attempt {attempt + 1}): {MODEL_NAME} with max_output_tokens={current_max_output_tokens}...") # Corrected logging
            response = await model.generate_content_async(
                contents=prompt_parts, 
                generation_config=generation_config_obj, 
                safety_settings=safety_settings_list
            )
            print("Received response from Gemini.")
            
            if response:
                if response.candidates:
                    candidate = response.candidates[0]
                    print(f"Candidate Finish Reason: {candidate.finish_reason}")
                    if hasattr(candidate, 'safety_ratings'): print(f"Candidate Safety Ratings: {candidate.safety_ratings}")
                    if hasattr(response, 'usage_metadata'): print(f"Usage Metadata: {response.usage_metadata}") # Moved here for context
                    
                    if candidate.finish_reason == 2: # MAX_TOKENS
                         print("Warning: Output truncated due to MAX_TOKENS limit.")
                    
                    if candidate.content and candidate.content.parts:
                        raw_generated_text = "".join(p.text for p in candidate.content.parts if hasattr(p, 'text') and p.text)
                        print(f"RAW LLM OUTPUT (first 500 chars):\n---\n{raw_generated_text[:500]}...\n---")
                        
                        generated_html = raw_generated_text
                        if generated_html.strip().startswith("```html"): generated_html = generated_html.strip()[7:]
                        if generated_html.strip().endswith("```"): generated_html = generated_html.strip()[:-3]
                        
                        if not generated_html.strip() and candidate.finish_reason == 1: 
                             print("Warning: Generated HTML is empty after stripping markdown, though model stopped naturally.")
                        return generated_html.strip() 
                else: 
                    error_message = "LLM response did not contain candidates."
                    if hasattr(response, 'prompt_feedback') and response.prompt_feedback: error_message += f" Prompt feedback: {response.prompt_feedback}"
                    print(error_message); raise HTTPException(status_code=500, detail=error_message)
            else: 
                print("No response object received from Gemini."); raise HTTPException(status_code=500, detail="No response received from LLM.")
        
        except google.api_core.exceptions.ResourceExhausted as e_res_exhausted: # <<< CORRECTED EXCEPTION CATCHING
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


# --- API Endpoints (keep as before) ---
@app.on_event("startup")
async def startup_event():
    print("Application startup: Attempting to initialize Vertex AI...");
    os.makedirs(GENERATED_HTML_DIR_PATH, exist_ok=True)
    print(f"Generated HTML clones will be saved in: {GENERATED_HTML_DIR_PATH}")
    print(f"Cloned files will be served from: {STATIC_CLONES_PATH_PREFIX}")
    if not initialize_vertex_ai(): print("Startup: LLM functionality might be impaired.")
    else: print("Startup: Vertex AI initialization check complete.")

@app.post("/get-scraped-context", response_model=ScrapedContextResponse, summary="Scrape and Clean Website Context")
async def get_scraped_context_endpoint(req: UrlRequest):
    try:
        print(f"Scraping URL for tester context: {req.url}")
        context_data: ScrapedContext = await scrape_website_context(req.url)
        return ScrapedContextResponse(
            desktop_screenshot_base64=context_data.desktop_screenshot_base64,
            mobile_screenshot_base64=context_data.mobile_screenshot_base64,
            simplified_html=context_data.simplified_html,
            original_url=req.url
        )
    except HTTPException as http_exc: raise http_exc
    except Exception as e: print(f"Unexpected error in /get-scraped-context: {type(e).__name__} - {e}\n{traceback.format_exc()}"); raise HTTPException(status_code=500, detail=f"An unexpected server error occurred. Error: {str(e)}")

@app.post("/clone-website-and-save", response_model=ClonedHtmlFileResponse, summary="Clone Website and Save HTML to File")
async def clone_website_and_save_endpoint(req_body: UrlRequest, request: Request):
    try:
        print(f"Step 1: Scraping URL for cloning: {req_body.url}"); context_data: ScrapedContext = await scrape_website_context(req_body.url)
        if not context_data.simplified_html or "failed" in context_data.simplified_html.lower() or "empty" in context_data.simplified_html.lower():
            raise HTTPException(status_code=422, detail=f"HTML scraping/cleaning failed. HTML: {context_data.simplified_html[:200]}")
        
        ENABLE_LLM_CLONING = True 
        llm_generated_html = ""

        if ENABLE_LLM_CLONING:
            print("Step 2: Generating HTML with LLM...");
            llm_generated_html = await generate_html_with_llm(
                cleaned_html=context_data.simplified_html,
                desktop_screenshot_base64=context_data.desktop_screenshot_base64,
                mobile_screenshot_base64=context_data.mobile_screenshot_base64
            )
            print("Step 3: Received HTML from LLM processing.")
            if not llm_generated_html.strip():
                 print("Warning: LLM returned an effectively empty HTML string.")
        else:
            print("Step 2 & 3: LLM Cloning is disabled. Generating placeholder HTML.")
            llm_generated_html = f"<html><body><h1>Placeholder for {req_body.url}</h1><p>LLM cloning is currently disabled.</p></body></html>"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_url_part = req_body.url.split('//')[-1].split('/')[0].replace('.', '_').replace(':', '_')
        filename = f"clone_{sanitized_url_part}_{timestamp}.html"
        file_path = os.path.join(GENERATED_HTML_DIR_PATH, filename)
        
        try:
            with open(file_path, "w", encoding="utf-8") as f: f.write(llm_generated_html)
            print(f"Successfully saved cloned HTML to: {file_path}")
        except IOError as e: print(f"Error saving HTML file: {e}\n{traceback.format_exc()}"); raise HTTPException(status_code=500, detail=f"Failed to save generated HTML file. Error: {str(e)}")
        
        base_url_parts = request.url.components
        base_url = f"{base_url_parts.scheme}://{base_url_parts.netloc}"
        view_link_path = f"{STATIC_CLONES_PATH_PREFIX}/{filename}"
        view_link = f"{base_url}{view_link_path}"
        
        return ClonedHtmlFileResponse(
            message="Website cloned and HTML saved." if ENABLE_LLM_CLONING else "Placeholder HTML generated.",
            file_path=file_path,
            view_link=view_link
        )
    except HTTPException as http_exc: raise http_exc
    except ValueError as ve: print(f"Configuration or Value error: {ve}\n{traceback.format_exc()}"); raise HTTPException(status_code=500, detail=str(ve))
    except Exception as e: print(f"Unexpected error in /clone-website-and-save: {type(e).__name__} - {e}\n{traceback.format_exc()}"); raise HTTPException(status_code=500, detail=f"An unexpected server error occurred. Error: {str(e)}")

@app.get("/gallery-items", response_model=GalleryResponse, summary="Get Items for Website Clone Gallery")
async def get_gallery_items(request: Request):
    items = []; base_url_parts = request.url.components; base_url = f"{base_url_parts.scheme}://{base_url_parts.netloc}"
    gallery_data_map = {
        "Landing Pages": [
            {"id": "ola", "filename": "clone_www_olacabs_com_20250605_183343.html", "title": "Ola Cabs", "description": "Ride Hailing Service"},
            {"id": "wix", "filename": "clone_www_wix_com_20250605_190834.html", "title": "Wix.com", "description": "Website Builder"},
            {"id": "wordpress", "filename": "clone_wordpress_com_20250605_222253.html", "title": "WordPress.com", "description": "Blogging Platform"}],
        "Portfolio Websites": [
            {"id": "simplegreet", "filename": "clone_simple-greetings-1748253405653_vercel_app_20250605_193006.html", "title": "Simple Greetings", "description": "Portfolio Example"}],
        "Ecommerce Sites": [
            {"id": "uber", "filename": "clone_www_uber_com_20250605_175014.html", "title": "Uber.com", "description": "Ride & Delivery"}]}
    for category, cat_items in gallery_data_map.items():
        for item_data in cat_items:
            local_file_path = os.path.join(GENERATED_HTML_DIR_PATH, item_data["filename"])
            if not os.path.exists(local_file_path):
                 print(f"Gallery item file missing, creating placeholder for: {item_data['filename']}")
                 try:
                     with open(local_file_path, "w", encoding="utf-8") as f_placeholder:
                         f_placeholder.write(f"<html><body><h1>Placeholder for {item_data['title']}</h1><p>File: {item_data['filename']}</p></body></html>")
                 except IOError:
                     print(f"Could not create placeholder for {item_data['filename']}")
            items.append(GalleryItem(id=item_data["id"], filename=item_data["filename"], view_link=f"{base_url}{STATIC_CLONES_PATH_PREFIX}/{item_data['filename']}", category=category, title=item_data["title"], description=item_data.get("description")))
    return GalleryResponse(items=items)

@app.get("/tester", response_class=FileResponse, summary="Get the Test Dashboard Page for Scraping Context")
async def get_test_dashboard():
    current_dir = os.path.dirname(os.path.abspath(__file__)); tester_path = os.path.join(current_dir, "tester.html") 
    if not os.path.exists(tester_path):
        alt_tester_path = os.path.join(current_dir, "..", "tester.html") 
        if os.path.exists(alt_tester_path): tester_path = alt_tester_path
        else: raise HTTPException(status_code=404, detail=f"tester.html not found at {tester_path} or {alt_tester_path}")
    return FileResponse(tester_path)

@app.get("/", summary="Health Check")
async def health_check(): return {"message": f"Orchids Website Cloner API (v0.3.1) is live! Model: {MODEL_NAME}, Project: {GCP_PROJECT_ID}"}

if __name__ == "__main__":
    print(f"Starting Orchids Website Cloner API with Uvicorn."); print(f"GCP Project: {GCP_PROJECT_ID}, Location: {GCP_LOCATION}, Model: {MODEL_NAME}")
    if not GCP_PROJECT_ID: print("WARNING: GCP_PROJECT_ID is not defined (hardcoded).")
    if not _vertex_ai_initialized: initialize_vertex_ai()
    uvicorn.run(app, host="0.0.0.0", port=8000)