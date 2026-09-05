# appointments/renderers.py
"""
Same rationale as health/renderers.py: the mobile client's
appointments.ts sends/expects camelCase JSON (nutritionistId,
appointmentType, availableSlots, meetingUrl...). Scoped to just the
appointments app's views rather than project-wide settings.py.

Requires: djangorestframework-camel-case (see requirements.txt)
"""
from djangorestframework_camel_case.parser import CamelCaseJSONParser
from djangorestframework_camel_case.render import CamelCaseJSONRenderer


class CamelCaseAPIMixin:
    """
    Mix into any DRF view/viewset to accept camelCase request bodies
    and emit camelCase response bodies, while everything internal
    (models, serializer field names) stays normal snake_case Python.
    """
    renderer_classes = [CamelCaseJSONRenderer]
    parser_classes = [CamelCaseJSONParser]
