class LinkNotFoundError(Exception):
    pass


class InvalidFriendLinkStatusError(Exception):
    pass


class SiteNavItemNotFoundError(Exception):
    pass


class InvalidSiteNavItemValueError(Exception):
    pass


class DuplicateFriendLinkApplicationError(Exception):
    pass


class FriendLinkApplicationLimitExceededError(Exception):
    pass
