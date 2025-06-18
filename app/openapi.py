"""Custom OpenAPI schema configuration.

Provides customized OpenAPI documentation with Bearer token authentication.
"""

from fastapi.openapi.utils import get_openapi


def custom_openapi(app):
    """Generate custom OpenAPI schema with Bearer authentication.
    
    Args:
        app: FastAPI application instance.
        
    Returns:
        dict: OpenAPI schema dictionary.
    """
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description=app.description,
        routes=app.routes,
    )
    
    openapi_schema.setdefault("components", {})
    openapi_schema["components"].setdefault("securitySchemes", {})

    # Add global security requirement for Bearer token authentication
    openapi_schema["security"] = [{"BearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema
