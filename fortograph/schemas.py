"""Tool schemas for the Fortograph plugin."""

SHAPE = {
    "type": "object",
    "description": (
        "One redaction region in image pixel coordinates. Use a rectangle "
        "(x, y, width, height), a circle (x, y, radius), or text (x, y, text)."
    ),
    "properties": {
        "shape": {
            "type": "string",
            "enum": ["rectangle", "circle", "text"],
            "description": "Region kind.",
        },
        "color": {
            "type": "string",
            "description": "Fill color as a hex string, e.g. '#000000'.",
        },
        "coordinates": {
            "type": "object",
            "description": "Pixel coordinates for the region.",
            "properties": {
                "x": {"type": "integer", "description": "Left/top x offset."},
                "y": {"type": "integer", "description": "Top y offset."},
                "width": {"type": "integer", "description": "Rectangle width."},
                "height": {"type": "integer", "description": "Rectangle height."},
                "radius": {"type": "integer", "description": "Circle radius."},
            },
            "required": ["x", "y"],
        },
        "text": {"type": "string", "description": "Text to draw (shape='text')."},
        "fontSize": {"type": "string", "description": "Font size for text."},
        "fontType": {"type": "string", "description": "Font family for text."},
    },
    "required": ["shape", "coordinates"],
}

STATUS = {
    "name": "fortograph_status",
    "description": (
        "Check whether the configured remote Fortograph API is reachable. "
        "Returns the resolved base URL, API endpoint, and HTTP status."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

REDACT = {
    "name": "fortograph_redact",
    "description": (
        "Redact one or more regions of a local image by uploading it to the "
        "remote Fortograph API and saving the processed copy. The password "
        "encrypts the redaction payload so fortograph_unredact can restore it later."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Absolute or relative path to the local image to redact.",
            },
            "regions": {
                "type": "array",
                "description": "Non-empty list of regions to redact.",
                "items": SHAPE,
                "minItems": 1,
            },
            "password": {
                "type": "string",
                "description": "Redaction password. Defaults to the plugin's FORTOGRAPH_PASSWORD secret.",
            },
            "action": {
                "type": "string",
                "enum": ["fortographthumbnail", "fortograph", "fortographregiononly"],
                "description": "Redaction mode. Defaults to fortographthumbnail.",
            },
            "output_path": {
                "type": "string",
                "description": "Where to save the result. Defaults to the input directory with a server-provided name.",
            },
        },
        "required": ["image_path", "regions"],
    },
}

UNREDACT = {
    "name": "fortograph_unredact",
    "description": (
        "Restore regions of a previously Fortograph-redacted image by uploading it "
        "to the remote Fortograph API and saving the recovered copy. Requires the "
        "same password that was used to redact it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the redacted local image.",
            },
            "password": {
                "type": "string",
                "description": "Redaction password. Defaults to the plugin's FORTOGRAPH_PASSWORD secret.",
            },
            "action": {
                "type": "string",
                "enum": ["unfortographthumbnail", "unfortograph", "unfortographregiononly"],
                "description": "Unredaction mode. Defaults to unfortographthumbnail.",
            },
            "output_path": {
                "type": "string",
                "description": "Where to save the result. Defaults to the input directory with a server-provided name.",
            },
        },
        "required": ["image_path"],
    },
}
