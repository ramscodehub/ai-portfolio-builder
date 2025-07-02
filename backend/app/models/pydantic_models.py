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

class PortfolioBuildConfig(BaseModel):
    reference_url: str = Field(
        ..., 
        example="https://www.some-cool-portfolio.com",
        description="The URL of the portfolio to use as a style reference."
    )
    resume_text: str = Field(
        ..., 
        example="John Doe\nSoftware Engineer at Tech Corp\nSkills: Python, React, AWS",
        description="The user's full resume or profile information as a block of text."
    )