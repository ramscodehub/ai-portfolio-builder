# backend/app/services/scraper_service.py
import base64
import asyncio
import traceback
from bs4 import BeautifulSoup, Comment
from playwright.async_api import async_playwright, Route
from playwright_stealth import stealth_async
from fastapi import HTTPException

import os
from app.models.pydantic_models import ScrapedContext
from app.core import config # Import config to get BASE_DIR
# Import the internal Pydantic model
from app.models.pydantic_models import ScrapedContext
    
def clean_html_for_llm(html_content: str) -> str:
    if not html_content: return "<!-- HTML content was empty -->"
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. Remove ONLY non-visual/behavioral tags. 
        # WE KEEP: 'style', 'link' (for CSS), 'svg' (for icons)
        tags_to_remove = ["script", "noscript", "meta", "iframe", "canvas"]
        for tag_name in tags_to_remove:
            for t in soup.find_all(tag_name): t.decompose()
            
        # 2. Remove comments
        for comment_tag in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment_tag.extract()

        # 3. Simplify Pictures/Images (Your original logic was good, just kept here)
        for picture_tag in soup.find_all('picture'):
            img_tag = picture_tag.find('img')
            if img_tag:
                source_to_use = None; sources = picture_tag.find_all('source')
                for s in sources:
                    if s.has_attr('srcset'):
                        first_src = s['srcset'].split(',')[0].strip().split(' ')[0]
                        if not source_to_use: source_to_use = first_src
                if source_to_use: img_tag['src'] = source_to_use
                
                # Keep classes and styles on images
                allowed_img = ['src', 'alt', 'class', 'style', 'id'] 
                for attr in list(img_tag.attrs):
                    if attr not in allowed_img: del img_tag[attr]
                picture_tag.replace_with(img_tag)
            else: picture_tag.decompose()

        # 4. Global Attribute Cleaning
        # CRITICAL: We must allow 'class' and 'style' globally
        allowed_attributes = {
            "a": ["href", "target"],
            "img": ["src", "alt", "width", "height"],
            "input": ["type", "value", "placeholder", "checked"],
        }
        
        global_allowed = ["id", "class", "style", "role", "aria-label"]

        for tag in soup.find_all(True):
            current_attrs = list(tag.attrs.keys()) # Copy keys to avoid iteration error
            
            for attr in current_attrs:
                # Keep global attributes (class, style, id)
                if attr in global_allowed:
                    continue
                
                # Keep specific attributes for specific tags
                if tag.name in allowed_attributes and attr in allowed_attributes[tag.name]:
                    continue
                
                # Remove everything else (data-attributes, event listeners like onclick, etc.)
                del tag[attr]

        # 5. Return the whole HTML, not just body (so we keep <head> styles)
        return soup.prettify()

    except Exception as e:
        print(f"Error cleaning HTML: {e}")
        return f"<!-- HTML cleaning failed: {str(e)} -->"


async def scrape_website_context(url: str, retries: int = 1) -> ScrapedContext:
    last_exception = None
    browser = None
    
    for attempt in range(retries + 1):
        try:
            async with async_playwright() as p:
                print(f"Attempt {attempt + 1}: Launching browser...")
                
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process',
                        '--disable-web-security'
                    ]
                )
                
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36", # Use a current User-Agent
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    bypass_csp=True,  # Bypass Content Security Policy
                    ignore_https_errors=True,
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": '"macOS"',
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1"
                    }
                )
                
                page = await context.new_page()
                
                # Apply a minimal, custom stealth script instead of the full library
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """)
                
                print(f"Navigating to {url}...")
                response = await page.goto(url, wait_until="load", timeout=10000)
                
                if response:
                    print(f"Initial response status: {response.status}")
                
                # A very long, patient wait for client-side JavaScript to render
                print("Performing long static wait for SPA hydration (10 seconds)...")
                await page.wait_for_timeout(10000)
                
                # Optional: Scroll down to trigger lazy-loaded elements
                try:
                    print("Scrolling page to trigger lazy-loading...")
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(2000) # Wait for content to load
                    await page.evaluate("window.scrollTo(0, 0)") # Scroll back up
                    await page.wait_for_timeout(1000)
                except Exception as scroll_err:
                    print(f"Could not scroll page, continuing anyway: {scroll_err}")

                print("Taking desktop screenshot...")
                desktop_buffer = await page.screenshot(full_page=True, timeout=30000)
                
                print("Taking mobile screenshot...")
                await page.set_viewport_size({"width": 390, "height": 844})
                await page.wait_for_timeout(1500) # Wait for resize
                mobile_buffer = await page.screenshot(full_page=True, timeout=30000)
                
                desktop_base64 = base64.b64encode(desktop_buffer).decode('utf-8')
                mobile_base64 = base64.b64encode(mobile_buffer).decode('utf-8')
                
                print("Extracting and cleaning HTML content...")
                html_content_raw = await page.content() # Get full page content
                
                if not html_content_raw or len(html_content_raw) < 200 or "Application error" in html_content_raw:
                    print("Scraped content is empty or an error page. Failing this attempt.")
                    raise ValueError("Scraped content was an empty or known error page.")
                
                simplified_html_output = clean_html_for_llm(html_content_raw)
                
                await browser.close()
                browser = None
                
                return ScrapedContext(
                    desktop_screenshot_base64=desktop_base64,
                    mobile_screenshot_base64=mobile_base64,
                    simplified_html=simplified_html_output
                )
                
        except Exception as e:
            print(f"Error during scraping attempt {attempt + 1} for {url}: {type(e).__name__} - {e}\n{traceback.format_exc()}")
            last_exception = e
            if browser and browser.is_connected():
                await browser.close()
            if attempt < retries:
                await asyncio.sleep(3)
            else:
                raise HTTPException(status_code=422, detail=f"Failed to scrape the reference URL after multiple attempts. It may be heavily protected or incompatible. Final error: {str(last_exception)}")
    
    raise HTTPException(status_code=500, detail="Scraping failed unexpectedly after all attempts.")