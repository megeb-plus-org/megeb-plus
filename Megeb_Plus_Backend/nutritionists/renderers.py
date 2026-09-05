# nutritionists/renderers.py
"""
Same rationale as health/renderers.py: the mobile client expects
camelCase JSON (yearsOfExperience, consultationFee, isVerified...).
Scoped to just the nutritionists app's views rather than project-wide
settings.py.

Requires: djangorestframework-camel-case (see requirements.txt)
"""
from djangorestframework_camel_case.parser import (
    CamelCaseFormParser,
    CamelCaseJSONParser,
    CamelCaseMultiPartParser,
)
from djangorestframework_camel_case.render import CamelCaseJSONRenderer


class CamelCaseAPIMixin:
    """
    Mix into any DRF view/viewset to accept camelCase request bodies
    and emit camelCase response bodies, while everything internal
    (models, serializer field names) stays normal snake_case Python.
    """
    renderer_classes = [CamelCaseJSONRenderer]
    parser_classes = [CamelCaseJSONParser]


class CamelCaseMultipartAPIMixin:
    """
    Same as CamelCaseAPIMixin, but for views that accept file uploads
    (multipart/form-data) instead of raw JSON — e.g. the nutritionist
    application form, which uploads license/credential/insurance/degree
    documents alongside camelCase text fields.
    """
    renderer_classes = [CamelCaseJSONRenderer]
    parser_classes = [CamelCaseMultiPartParser, CamelCaseFormParser]
