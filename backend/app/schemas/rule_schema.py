from pydantic import BaseModel
from typing import List

class DetectionFilterUpdate(BaseModel):
    ignored_classes: List[str]

class RestrictedAreaUpdate(BaseModel):
    enabled: bool

class ControlsResponse(BaseModel):
    ignored_classes: List[str]
    restricted_area_enabled: bool
