def test_ios_android_capability_flags():
    from app.integrations.ios import IOSIntegration
    from app.integrations.android import AndroidIntegration

    ios = {c.name: c for c in IOSIntegration(user_id="u").capabilities()}
    assert ios["screen_time"].available is False
    assert ios["motion_activity"].available is True
    assert "no implemented collection path" in ios["screen_time"].reason.lower()
    assert "coremotion" in ios["motion_activity"].reason.lower()

    android = {c.name: c for c in AndroidIntegration(user_id="u").capabilities()}
    assert android["app_usage_stats"].available is False
    assert android["app_usage_stats"].reason == "companion does not collect usage stats yet"
