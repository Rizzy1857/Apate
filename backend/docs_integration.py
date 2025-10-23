"""
FastAPI Documentation Integration

This script configures and enables comprehensive API documentation 
for the Apate Honeypot platform using OpenAPI/Swagger.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from typing import Dict, Any
from .api_docs import OPENAPI_CONFIG, API_TAGS, ENDPOINT_DOCS, SECURITY_SCHEMES

def configure_openapi_docs(app: FastAPI) -> None:
    """
    Configure comprehensive OpenAPI documentation for the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    
    # Update app metadata
    app.title = OPENAPI_CONFIG["title"]
    app.description = OPENAPI_CONFIG["description"] 
    app.version = OPENAPI_CONFIG["version"]
    app.contact = OPENAPI_CONFIG["contact"]
    app.license_info = OPENAPI_CONFIG["license_info"]
    app.servers = OPENAPI_CONFIG["servers"]
    app.openapi_tags = API_TAGS

def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """
    Generate custom OpenAPI schema with enhanced documentation.
    
    Args:
        app: FastAPI application instance
        
    Returns:
        Enhanced OpenAPI schema dictionary
    """
    #The below code is yet to be tested and adjusted as per the actual app structure.
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = SECURITY_SCHEMES
    
    # Enhance endpoint documentation
    for path, methods in openapi_schema["paths"].items():
        if path in ENDPOINT_DOCS:
            endpoint_doc = ENDPOINT_DOCS[path]
            for method, details in methods.items():
                if "summary" in endpoint_doc:
                    details["summary"] = endpoint_doc["summary"]
                if "description" in endpoint_doc:
                    details["description"] = endpoint_doc["description"]
                if "responses" in endpoint_doc:
                    details["responses"].update(endpoint_doc["responses"])
                if "request_body" in endpoint_doc:
                    details["requestBody"] = endpoint_doc["request_body"]
    
    # Add example responses
    add_example_responses(openapi_schema)
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

def add_example_responses(schema: Dict[str, Any]) -> None:
    """
    Add comprehensive example responses to the OpenAPI schema.
    
    Args:
        schema: OpenAPI schema dictionary to enhance
    """
    
    # Standard error responses for all endpoints
    error_responses = {
        "400": {
            "description": "Bad Request",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Invalid request parameters",
                        "code": 400,
                        "timestamp": "2024-12-24T10:30:00Z"
                    }
                }
            }
        },
        "429": {
            "description": "Rate Limit Exceeded", 
            "content": {
                "application/json": {
                    "example": {
                        "error": "Rate limit exceeded. Try again later.",
                        "code": 429,
                        "timestamp": "2024-12-24T10:30:00Z"
                    }
                }
            }
        },
        "500": {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal server error",
                        "code": 500,
                        "timestamp": "2024-12-24T10:30:00Z"
                    }
                }
            }
        }
    }
    
    # Add standard error responses to all endpoints
    for path_info in schema["paths"].values():
        for method_info in path_info.values():
            if "responses" not in method_info:
                method_info["responses"] = {}
            method_info["responses"].update(error_responses)

def setup_swagger_ui_config() -> Dict[str, Any]:
    """
    Configure Swagger UI with custom settings for better UX.
    
    Returns:
        Swagger UI configuration dictionary
    """
    return {
        "deepLinking": True,
        "displayOperationId": True,
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
        "defaultModelRendering": "model",
        "displayRequestDuration": True,
        "docExpansion": "list",
        "filter": True, # Enable filtering of endpoints
        "operationsSorter": "alpha", # Sort operations alphabetically
        "tagsSorter": "alpha", # Sort tags alphabetically
        "showExtensions": True, # Enable display of vendor extensions
        "showCommonExtensions": True, # Show common extensions like x-code-samples
        "tryItOutEnabled": True,    # Enable "Try it out" functionality
        "requestSnippetsEnabled": True, # Enable request snippets
        "requestSnippets": {
            "generators": {
                "curl_bash": {
                    "title": "cURL (bash)",
                    "syntax": "bash"
                },
                "curl_powershell": {
                    "title": "cURL (PowerShell)",
                    "syntax": "powershell"
                },
                "curl_cmd": {
                    "title": "cURL (CMD)",
                    "syntax": "bash"
                }
            },
            "defaultExpanded": True,
            "languages": ["curl_bash", "curl_powershell", "curl_cmd"]
        }
    }

# Usage example for integration with main FastAPI app
"""
from backend.docs_integration import configure_openapi_docs, custom_openapi, setup_swagger_ui_config

app = FastAPI()

# Configure documentation
configure_openapi_docs(app)

# Set custom OpenAPI schema
app.openapi = lambda: custom_openapi(app)

# The Swagger UI will be automatically available at:
# - /docs (Swagger UI)
# - /redoc (ReDoc)
"""