# backend/app/services/scraper_service.py
import base64
import asyncio
import traceback
from bs4 import BeautifulSoup, Comment
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from fastapi import HTTPException

import os
from app.models.pydantic_models import ScrapedContext
from app.core import config # Import config to get BASE_DIR
# Import the internal Pydantic model
from app.models.pydantic_models import ScrapedContext

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
    except Exception as e:
        print(f"Error during HTML cleaning: {e}\n{traceback.format_exc()}")
        return f"<!-- HTML cleaning process failed: {str(e)} -->"

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