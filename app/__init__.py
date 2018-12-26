import connexion


app = connexion.App(__name__)
app.add_api('../openapi.yaml')

application = app.app
