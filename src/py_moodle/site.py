"""Site information."""

from dataclasses import dataclass, fields
from typing import Any, Dict, List, Optional

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
    usercanchangeconfig: Optional[bool] = None
    usercanviewconfig: Optional[bool] = None
    sitesecret: Optional[str] = None
    usersessionscount: Optional[int] = None

    @classmethod
    def from_moodle(cls, data: Dict[str, Any]) -> "SiteInfo":
        """Build site information from a Moodle webservice response.

        Unknown fields are ignored so new Moodle versions can extend
        ``core_webservice_get_site_info`` without breaking the client.

        Args:
            data: Raw site-info payload returned by Moodle.

        Returns:
            SiteInfo: Parsed site information.
        """
        known_fields = {field.name for field in fields(cls)}
        values = {key: value for key, value in data.items() if key in known_fields}
        return cls(**values)


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
    return SiteInfo.from_moodle(response)
