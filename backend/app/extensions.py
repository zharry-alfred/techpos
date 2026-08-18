from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()

try:
    from flask_marshmallow import Marshmallow
    ma = Marshmallow()
except ImportError:
    class DummyMarshmallow:
        def init_app(self, app):
            pass
    ma = DummyMarshmallow()
