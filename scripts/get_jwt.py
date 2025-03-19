"""Get JWT from environment variable."""
import jwt
from dotenv import load_dotenv
import os

# Load the environment variables from the .env file
load_dotenv() 

def get_jwt(jwt_name: str) -> str:
    """Get JWT from environment variable."""   
    return os.getenv(jwt_name)