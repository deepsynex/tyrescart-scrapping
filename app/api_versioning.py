"""
app/api_versioning.py - API Version Control & Semantic Versioning Middleware
Provides API versioning metadata, negotiation, response headers, and manifest endpoints.
"""

from datetime import datetime, timezone
from flask import jsonify, request, Response

# ============================================================================
# API VERSION CONFIGURATION & MANIFEST
# ============================================================================

API_VERSION = "1.0.0"
API_RELEASE_TAG = "v1"
API_RELEASE_DATE = "2026-08-29"
SUPPORTED_API_VERSIONS = ["v1", "1.0", "1.0.0"]
DEPRECATED_API_VERSIONS = []

API_MODULE_MANIFEST = {
    "name": "TyresVision Executive REST API",
    "version": API_VERSION,
    "api_version_tag": API_RELEASE_TAG,
    "release_date": API_RELEASE_DATE,
    "supported_versions": SUPPORTED_API_VERSIONS,
    "deprecated": False,
    "status": "stable",
    "surfaces": {
        "client": {
            "name": "Storefront Public API",
            "base_url": "/api/v1",
            "unversioned_fallback": "/api",
            "routes": [
                {"path": "/api/v1/blogs", "method": "GET", "desc": "List published blogs with pagination"},
                {"path": "/api/v1/blogs/<slug>", "method": "GET", "desc": "Fetch single blog post by slug"},
                {"path": "/api/v1/version", "method": "GET", "desc": "API version manifest"}
            ]
        },
        "visionadmin": {
            "name": "VisionAdmin CMS Studio API",
            "base_url": "/visionadmin/api/v1",
            "unversioned_fallback": "/visionadmin/api",
            "routes": [
                {"path": "/visionadmin/api/v1/pages", "methods": ["GET", "POST"], "desc": "Page CRUD & metrics"},
                {"path": "/visionadmin/api/v1/pages/<id>", "methods": ["GET", "PUT", "DELETE"], "desc": "Single page management"},
                {"path": "/visionadmin/api/v1/sections", "methods": ["GET", "POST"], "desc": "Page sections builder"},
                {"path": "/visionadmin/api/v1/sections/reorder", "method": "POST", "desc": "Section drag-and-drop sort"},
                {"path": "/visionadmin/api/v1/blogs", "methods": ["GET", "POST"], "desc": "Blog articles management"},
                {"path": "/visionadmin/api/v1/global-search", "method": "GET", "desc": "Universal deep CMS search"},
                {"path": "/visionadmin/api/v1/settings/reviewer", "methods": ["GET", "POST"], "desc": "Expert reviewer configuration"},
                {"path": "/visionadmin/api/v1/version", "method": "GET", "desc": "VisionAdmin API version manifest"}
            ]
        },
        "tcsadmin": {
            "name": "Scraper Admin & Operations API",
            "base_url": "/tcsadmin/api/v1",
            "unversioned_fallback": "/tcsadmin/api",
            "routes": [
                {"path": "/api/v1/files", "methods": ["GET", "POST"], "desc": "Scraper management endpoints"},
                {"path": "/api/v1/scraper/analyze", "method": "POST", "desc": "Scraper input URL analysis"}
            ]
        }
    }
}


def get_version_manifest(surface: str = "all") -> dict:
    """Returns the version control manifest and status."""
    manifest = {
        "success": True,
        "api_name": API_MODULE_MANIFEST["name"],
        "api_version": API_VERSION,
        "release_tag": API_RELEASE_TAG,
        "release_date": API_RELEASE_DATE,
        "status": "healthy",
        "supported_versions": SUPPORTED_API_VERSIONS,
        "deprecated_versions": DEPRECATED_API_VERSIONS,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if surface == "all":
        manifest["surfaces"] = API_MODULE_MANIFEST["surfaces"]
    elif surface in API_MODULE_MANIFEST["surfaces"]:
        manifest["surface"] = API_MODULE_MANIFEST["surfaces"][surface]
    return manifest


def check_requested_api_version() -> tuple:
    """
    Checks if the client sent an explicit 'X-API-Version' or 'Accept-Version' header.
    Returns (is_valid, error_response_or_None, version_str).
    """
    req_ver = request.headers.get("X-API-Version") or request.headers.get("Accept-Version")
    if not req_ver:
        return True, None, API_RELEASE_TAG

    req_ver_clean = req_ver.strip().lower()
    if req_ver_clean in [v.lower() for v in SUPPORTED_API_VERSIONS]:
        return True, None, req_ver_clean

    error_body = {
        "success": False,
        "error": f"Requested API version '{req_ver}' is not supported.",
        "requested_version": req_ver,
        "current_version": API_VERSION,
        "supported_versions": SUPPORTED_API_VERSIONS
    }
    return False, (jsonify(error_body), 400), req_ver_clean


def inject_api_version_headers(response: Response) -> Response:
    """Injects standard API version control HTTP headers into API responses."""
    # Only tag API routes
    path = request.path
    if path.startswith("/api") or path.startswith("/visionadmin/api") or path.startswith("/tcsadmin/api"):
        response.headers["X-API-Version"] = API_VERSION
        response.headers["X-API-Release"] = API_RELEASE_TAG
        response.headers["X-API-Status"] = "active"
        response.headers["X-API-Deprecation"] = "none"
        response.headers["X-API-Documentation"] = "/api/v1/version"
    return response


def register_version_endpoints(app):
    """Registers /api/version, /api/v1/version, /visionadmin/api/version manifests."""

    @app.route('/api/version', methods=['GET'])
    @app.route('/api/v1/version', methods=['GET'])
    def api_version_manifest():
        return jsonify(get_version_manifest("all"))

    @app.route('/visionadmin/api/version', methods=['GET'])
    @app.route('/visionadmin/api/v1/version', methods=['GET'])
    def visionadmin_api_version_manifest():
        return jsonify(get_version_manifest("visionadmin"))

    @app.route('/tcsadmin/api/version', methods=['GET'])
    @app.route('/tcsadmin/api/v1/version', methods=['GET'])
    def tcsadmin_api_version_manifest():
        return jsonify(get_version_manifest("tcsadmin"))
