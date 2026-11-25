"""Check that a request was signed by our Netlify site."""

import jwt


def is_signed(token, secret):
    try:
        jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer="netlify",
            leeway=30,
            options={"require": ["exp", "iss"]},
        )
    except jwt.PyJWTError:
        return False
    return True
