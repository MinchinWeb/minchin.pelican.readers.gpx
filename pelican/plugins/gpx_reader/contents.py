from pelican.contents import Content


class GPX(Content):
    mandatory_properties = ("title", "date")
    allowed_statuses = (
        "published",
        "hidden",
    )
    default_status = "published"
    default_template = "article"
