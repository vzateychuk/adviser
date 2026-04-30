from flows.pec.schema_catalog import SchemaCatalog


def test_schema_catalog_loads_all_schemas():
    catalog = SchemaCatalog("flows/pec/schemas")
    ids = catalog.ids()
    # SchemaCatalog should load schemas from YAML files and return non-empty list
    assert isinstance(ids, list)
    assert len(ids) > 0


def test_schema_catalog_loads_valid_schema_structure():
    catalog = SchemaCatalog("flows/pec/schemas")
    ids = catalog.ids()
    # At least one schema should exist
    assert len(ids) > 0
    # Verify each loaded schema has required structure
    for schema_id in ids:
        schema = catalog.get(schema_id)
        assert schema is not None, f"Schema {schema_id} should be loadable"
        assert "schema_meta" in schema.raw, f"Schema {schema_id} must have schema_meta"
        assert "selection_hints" in schema.raw, f"Schema {schema_id} must have selection_hints"