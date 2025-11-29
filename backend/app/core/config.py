# backend/app/core/config.py
import os

# GCP Configuration
GCP_PROJECT_ID = "orchids-461923"
#GCP_LOCATION = "global"
GCP_LOCATION = 'us-central1'
MODEL_NAME = "gemini-2.5-pro"

# Directory Configuration
GENERATED_HTML_DIR_NAME = "generated_html_clones"
# The BASE_DIR will be the 'app' directory, since config.py is inside app/core/
# We go up one level to get to 'app'
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GENERATED_HTML_DIR_PATH = os.path.join(BASE_DIR, GENERATED_HTML_DIR_NAME)

# URL Path Prefix for serving static files
STATIC_CLONES_PATH_PREFIX = "/clones"

# S3 Configuration
S3_BUCKET_NAME = "ram-portfolio-clones"
CLOUD_FRONT_DOMAIN = "https://d12dmeynqgk1fi.cloudfront.net"

# CORS Origins
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
    "http://127.0.0.1:5500"
]