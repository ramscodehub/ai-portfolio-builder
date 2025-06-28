# backend/app/models/pydantic_models.py
from pydantic import BaseModel, Field

# For incoming requests
class UrlRequest(BaseModel):
    url: str = Field(..., example="https://www.example.com")

# For responses
class ScrapedContextResponse(BaseModel):
    desktop_screenshot_base64: str
    mobile_screenshot_base64: str
    simplified_html: str | None
    original_url: str

class ClonedHtmlFileResponse(BaseModel):
    message: str
    file_path: str
    view_link: str | None = None

class GalleryItem(BaseModel):
    id: str
    filename: str
    view_link: str
    category: str
    title: str
    description: str | None = None

class GalleryResponse(BaseModel):
    items: list[GalleryItem]

# For internal data transfer between services
class ScrapedContext(BaseModel):
    desktop_screenshot_base64: str
    mobile_screenshot_base64: str
    simplified_html: str | None