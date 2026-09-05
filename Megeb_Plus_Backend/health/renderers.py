# health/renderers.py
"""
The mobile client (Natati's repo) sends/expects camelCase JSON
(caloriesPer100g, proteinG, waterTargetGlasses...). Django/DRF
convention is snake_case (calories_per_100g, protein_g...).

Rather than changing project-wide settings.py (out of scope — we were
asked not to touch anything outside the health app), this mixin scopes
camelCase conversion to just the health app's views. Every viewset/
APIView in health/views.py uses it.

Requires: pip install djangorestframework-camel-case
(add it to requirements.txt)
"""
from djangorestframework_camel_case.parser import CamelCaseJSONParser
from djangorestframework_camel_case.render import CamelCaseJSONRenderer


class CamelCaseAPIMixin:
    """
    Mix into any DRF view/viewset to accept camelCase request bodies
    and emit camelCase response bodies, while everything internal
    (models, serializer field names) stays normal snake_case Python.

    Field names that don't just differ by casing (e.g. model's
    `activity_type` vs mobile's `activity`) are NOT fixed by this —
    those are handled with explicit `source=` aliases in serializers.py.
    """
    renderer_classes = [CamelCaseJSONRenderer]
    parser_classes = [CamelCaseJSONParser]
