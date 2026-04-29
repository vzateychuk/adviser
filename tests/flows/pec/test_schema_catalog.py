from flows.pec.schema_catalog import SchemaCatalog


def test_schema_catalog_loads_all_schemas():
    catalog = SchemaCatalog("flows/pec/schemas")
    ids = catalog.ids()
    assert ids == ["consultation", "diagnostic", "lab", "medication_trace"]


def test_schema_catalog_lab_contract_contains_required_blocks():
    schema = SchemaCatalog("flows/pec/schemas").get("lab")
    # Check that the schema has the expected structure
    assert "schema_meta" in schema.raw
    assert schema.raw["schema_meta"]["id"] == "lab"
    assert "selection_hints" in schema.raw