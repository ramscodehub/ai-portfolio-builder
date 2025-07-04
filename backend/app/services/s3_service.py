import boto3
from botocore.exceptions import NoCredentialsError
from fastapi import HTTPException
import traceback

from app.core import config

def upload_html_to_s3(html_content: str, filename: str) -> str:
    """
    Uploads a string of HTML content to a public S3 bucket.

    Args:
        html_content: The HTML string to upload.
        filename: The desired filename for the object in S3.

    Returns:
        The public URL of the uploaded file.
    
    Raises:
        HTTPException: If the upload fails due to credentials or other AWS errors.
    """
    print(f"Uploading {filename} to S3 bucket: {config.S3_BUCKET_NAME}")
    
    try:
        s3_client = boto3.client('s3')
        
        # Upload the string content directly to the S3 bucket
        s3_client.put_object(
            Bucket=config.S3_BUCKET_NAME,
            Key=filename,
            Body=html_content,
            ContentType='text/html' # Set the correct MIME type for browsers
        )
        print("Successfully uploaded to S3.")

        view_link = f"{config.CLOUD_FRONT_DOMAIN}/{filename}"
        print(f"Public CloudFront URL: {view_link}")
        return view_link

    except NoCredentialsError:
        print("ERROR: AWS credentials not found. Configure AWS CLI (`aws configure`) or environment variables.")
        raise HTTPException(
            status_code=500, 
            detail="Server is not configured for AWS uploads. Credentials missing."
        )
    except Exception as e:
        print(f"ERROR uploading to S3: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to upload generated file to cloud storage. Error: {str(e)}"
        )