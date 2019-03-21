from quetzal.app.models import (
    Family, MetadataQuery, Metadata, User, Role, Workspace
)


def test_registry(db):
    """Test that models are correctly registered"""
    class_registry = getattr(db.Model, '_decl_class_registry', {})
    registered_set = set(cls for cls in class_registry.values()
                         if isinstance(cls, type) and issubclass(cls, db.Model))
    expected_set = {Family, Metadata, MetadataQuery, User, Role, Workspace}
    assert registered_set == expected_set
