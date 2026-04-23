from flows.pec.schema_catalog import SchemaCatalog



def test_schema_catalog_loads_all_schemas():
    catalog = SchemaCatalog("flows/pec/schemas")
    ids = catalog.ids()
    assert ids == ["consultation", "diagnostic", "lab", "medication_trace"]



def test_schema_catalog_lab_contract_contains_required_blocks():
    schema = SchemaCatalog("flows/pec/schemas").get("lab")
    assert "document" in schema.required_blocks
    assert "patient" in schema.required_blocks
    assert "laboratory_panel" in schema.required_blocks
    assert any("numeric" in rule for rule in schema.critic_rules)
