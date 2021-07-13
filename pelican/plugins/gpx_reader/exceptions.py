class TooShortGPXException(ValueError):
    """GPX has less than 2 points, and so won't generate a heatmap cleanly."""
