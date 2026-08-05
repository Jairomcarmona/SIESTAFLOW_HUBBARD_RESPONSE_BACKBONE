# Trazabilidad de requisitos

| Requisito | Documento principal | Esquema / artefacto | Prueba futura |
|---|---|---|---|
| Núcleo sin hardcodeo | COMPONENT_BOUNDARIES | campaign.schema.json | test_no_material_literals |
| Geometría inmutable | GEOMETRY_CONTRACT | geometry_identity.schema.json | mutate_coordinate |
| BARE demostrado | BARE_SCREENED_CONTRACT | runtime/response evidence | parser_fixture_bare |
| Matriz cuadrada | MATRIX_CONSTRUCTION_CONTRACT | matrix_bundle.schema.json | reject_rectangular |
| Gate antisimetría | NUMERICAL_GATES | gate_results.schema.json | inject_antisymmetry |
| Inversas y residuos | MATRIX_INVERSION_CONTRACT | matrix_bundle.schema.json | incompatible_inverse |
| Fórmula con resta | SCIENTIFIC_METHOD | matrix_bundle.schema.json | mutate_subtraction_to_sum |
| Caché por PSML/binario | TASK_IDENTITY_AND_CACHE | task.schema.json | mutate_psml |
| Estado separado | STATE_MACHINE | task_status.schema.json | exit_zero_unvalidated |
| Decisión humana | HUMAN_DECISION_CONTRACT | human_decision.schema.json | recommendation_without_decision |
