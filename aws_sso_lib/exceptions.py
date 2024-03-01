import collections

from botocore.exceptions import (
    SSOError,
    SSOTokenLoadError,
    UnauthorizedSSOTokenError,
)

from .vendored_botocore.exceptions import PendingAuthorizationExpiredError

class InvalidSSOConfigError(Exception):
    pass

class AuthDispatchError(Exception):
    pass

class AuthenticationNeededError(Exception):
    pass
