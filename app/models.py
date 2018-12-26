import enum

from sqlalchemy.sql import func

from app import db


class WorkspaceState(enum.Enum):
    INITIALIZING = 1
    READY = 2
    PROCESSING = 3
    INVALID = 4
    CONFLICT = 5
    DELETED = 6


class Workspace(db.Model):
    __tablename__ = 'workspaces'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), nullable=False)
    state = db.Column(db.Enum(WorkspaceState), nullable=False, default=WorkspaceState.INITIALIZING)
    description = db.Column(db.Text, nullable=False)
    creation_date = db.Column(db.DateTime(timezone=True), server_default=func.now())
    temporary = db.Column(db.Boolean, nullable=False, default=False)
    data_url = db.Column(db.String(2048), nullable=False)

    def __repr__(self):
        return f'<Workspace {self.id} [name="{self.name}" ' \
               f'state={self.state.name if self.state else "unset"}]>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state.name,
            'description': self.description,
            'creation_date': self.creation_date,
            'temporary': self.temporary,
            'data_url': self.data_url,
        }
