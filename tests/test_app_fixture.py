def test_app(app):
    """Minimal test to verify the app fixture is loaded"""
    assert app is not None
    assert app.config['TESTING']

def test_db(app, db):
    db.create_all()

