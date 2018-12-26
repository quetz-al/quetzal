from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import connexion

from config import config


# Application is initialized by connexion. Note that connexion is not a Flask
# extension; it wraps the Flask application entirely. The Flask application is
# accesible through app.app
app = connexion.App(__name__)
application = app.app
application.config.from_object(config.get(application.env))

# Database
print('Creating db')
db = SQLAlchemy(application)
print(f'db created {db}')
migrate = Migrate(application, db)

# APIs
app.add_api('../openapi.yaml', strict_validation=True, validate_responses=True)
