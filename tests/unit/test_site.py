"""Unit tests for Moodle site information parsing."""

from py_moodle.site import AdvancedFeature, SiteFunction, SiteInfo, get_site_info


class StubSession:
    """Return a deterministic site-info payload."""

    def __init__(self, payload):
        """Store the payload returned by the fake webservice call."""
        self.payload = payload

    def call(self, function):
        """Return the configured payload for the site-info function."""
        assert function == "core_webservice_get_site_info"
        return dict(self.payload)


def _site_info_payload():
    """Build a representative Moodle site-info response."""
    return {
        "sitename": "Test Site",
        "username": "admin",
        "firstname": "Admin",
        "lastname": "User",
        "fullname": "Admin User",
        "lang": "en",
        "userid": 2,
        "siteurl": "https://moodle.example.test",
        "userpictureurl": "https://moodle.example.test/pic.jpg",
        "functions": [
            {"name": "core_webservice_get_site_info", "version": "1.0"},
        ],
        "downloadfiles": 1,
        "uploadfiles": 1,
        "release": "5.3 (Build: 20261005)",
        "version": "2026100500",
        "mobilecssurl": "",
        "advancedfeatures": [{"name": "enablecompletion", "value": 1}],
        "usercanmanageownfiles": True,
        "userquota": 100000000,
        "usermaxuploadfilesize": 20971520,
        "userhomepage": 0,
        "userprivateaccesskey": "private-access-key-fake",
        "siteid": 1,
        "sitecalendartype": "gregorian",
        "usercalendartype": "gregorian",
        "userissiteadmin": True,
        "theme": "boost",
        "limitconcurrentlogins": 0,
        "policyagreed": 1,
        "usercanchangeconfig": True,
        "usercanviewconfig": True,
        "sitesecret": "site-secret-fake",
        "usersessionscount": 1,
        "futuremoodlefield": "ignored",
    }


def test_get_site_info_accepts_extended_moodle_payload():
    """New and unknown Moodle fields must not break site-info parsing."""
    site_info = get_site_info(StubSession(_site_info_payload()))

    assert isinstance(site_info, SiteInfo)
    assert site_info.usercanchangeconfig is True
    assert site_info.usercanviewconfig is True
    assert site_info.sitesecret == "site-secret-fake"
    assert site_info.usersessionscount == 1
    assert isinstance(site_info.functions[0], SiteFunction)
    assert isinstance(site_info.advancedfeatures[0], AdvancedFeature)
    assert not hasattr(site_info, "futuremoodlefield")
