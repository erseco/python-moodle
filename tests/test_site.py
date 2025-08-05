"""Tests for the site module."""
from py_moodle.session import MoodleSession
from py_moodle.site import SiteInfo, get_site_info


def test_get_site_info_real(request):
    """Test get_site_info in a real environment."""
    env = request.config.moodle_target.name
    ms = MoodleSession.get(env)
    site_info = get_site_info(ms)

    assert isinstance(site_info, SiteInfo)
    assert site_info.sitename is not None
    assert site_info.username is not None
    assert site_info.firstname is not None
    assert site_info.lastname is not None
    assert site_info.fullname is not None
    assert site_info.lang is not None
    assert site_info.userid is not None
    assert site_info.siteurl is not None
    assert site_info.userpictureurl is not None
    assert site_info.functions is not None
    assert site_info.downloadfiles is not None
    assert site_info.uploadfiles is not None
    assert site_info.release is not None
    assert site_info.version is not None
    assert site_info.mobilecssurl is not None
    assert site_info.advancedfeatures is not None
    assert site_info.usercanmanageownfiles is not None
    assert site_info.userquota is not None
    assert site_info.usermaxuploadfilesize is not None
    assert site_info.userhomepage is not None
    assert site_info.userprivateaccesskey is not None
    assert site_info.siteid is not None
    assert site_info.sitecalendartype is not None
    assert site_info.usercalendartype is not None
    assert site_info.userissiteadmin is not None
    assert site_info.theme is not None
    assert site_info.limitconcurrentlogins is not None
    assert site_info.policyagreed is not None
