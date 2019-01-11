def test_app(app):
    """Minimal test to verify the app fixture is loaded"""
    assert app is not None
    assert app.config['TESTING']
