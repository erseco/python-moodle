"""Site information."""

from dataclasses import dataclass
from typing import List

from py_moodle.session import MoodleSession


@dataclass
class SiteFunction:
    """A dataclass to represent a function available in the Moodle site."""

    name: str
    version: str


@dataclass
class AdvancedFeature:
    """A dataclass to represent an advanced feature available in the Moodle site."""

    name: str
    value: int


@dataclass
class SiteInfo:
    """A dataclass to represent the site information."""

    sitename: str
    username: str
    firstname: str
    lastname: str
    fullname: str
    lang: str
    userid: int
    siteurl: str
    userpictureurl: str
    functions: List[SiteFunction]
    downloadfiles: int
    uploadfiles: int
    release: str
    version: str
    mobilecssurl: str
    advancedfeatures: List[AdvancedFeature]
    usercanmanageownfiles: bool
    userquota: int
    usermaxuploadfilesize: int
    userhomepage: int
    userprivateaccesskey: str
    siteid: int
    sitecalendartype: str
    usercalendartype: str
    userissiteadmin: bool
    theme: str
    limitconcurrentlogins: int
    policyagreed: int


def get_site_info(session: MoodleSession) -> SiteInfo:
    """Get site info.

    Args:
        session (MoodleSession): The Moodle session.

    Returns:
        SiteInfo: The site information.
    """
    response = session.call("core_webservice_get_site_info")
    response["functions"] = [
        SiteFunction(**function) for function in response["functions"]
    ]
    response["advancedfeatures"] = [
        AdvancedFeature(**feature) for feature in response["advancedfeatures"]
    ]
    return SiteInfo(**response)
