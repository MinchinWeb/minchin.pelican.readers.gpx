from hashlib import md5

def gpx_hash(gpx):
    """
    Given a GPX track(s), returns a hash.

    Can be used to determine if two GPX tracks are the same.
    """
    return md5(str(gpx).encode()).hexdigest()
