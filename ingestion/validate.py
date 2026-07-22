import os
import great_expectations as gx
from great_expectations.core.batch import RuntimeBatchRequest
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / "docker" / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")

DB_URI = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:"
    f"{os.getenv('POSTGRES_PASSWORD')}@{DB_HOST}:{DB_PORT}/"
    f"{os.getenv('POSTGRES_DB')}"
)

def get_context():
    context = gx.get_context(context_root_dir="gx")
    return context

def build_expectation_suite(context):
    suite_name = "incidents_suite"
    context.add_or_update_expectation_suite(suite_name)

    batch_request = RuntimeBatchRequest(
        datasource_name="incidents_datasource",
        data_connector_name="default_runtime_data_connector",
        data_asset_name="incidents",
        runtime_parameters={
            "query": """
                SELECT
                    id, hazard_id, incident_on, loss_id,
                    ST_X(point) AS longitude,
                    ST_Y(point) AS latitude
                FROM incidents
            """
        },
        batch_identifiers={"default_identifier_name": "incidents_batch"},
    )

    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name=suite_name,
    )

    # --- The actual expectations ---

    # 1. id is never null and always unique (our upsert key)
    validator.expect_column_values_to_not_be_null("id")
    validator.expect_column_values_to_be_unique("id")

    # 2. hazard_id must be one of the known valid hazard IDs
    #    (belt-and-suspenders on top of the FK constraint — this gives us
    #    a readable report instead of a hard DB error)
    known_hazard_ids = list(range(1, 48))  # BIPAD's 47 hazards, IDs 1-47
    validator.expect_column_values_to_be_in_set("hazard_id", known_hazard_ids)

    # 3. incident_on should not be null
    validator.expect_column_values_to_not_be_null("incident_on")

    # 4. loss_id, if present, should be a positive integer (sanity check)
    validator.expect_column_values_to_be_between(
        "loss_id", min_value=1, max_value=None, mostly=1.0
    )

    # 5. Coordinates must fall within Nepal's actual geographic bounding box
    #    (catches corrupted or lat/lng-swapped coordinates)
    validator.expect_column_values_to_be_between(
        "latitude", min_value=26.3, max_value=30.5, mostly=0.98
    )
    validator.expect_column_values_to_be_between(
        "longitude", min_value=80.0, max_value=88.3, mostly=0.98
    )

    # 6. incident_on should not be implausibly in the future
    #    (a real data-quality signal if BIPAD ever sends a garbage date)
    import datetime
    validator.expect_column_values_to_be_between(
        "incident_on",
        min_value=None,
        max_value=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        mostly=1.0,
    )
    
    validator.save_expectation_suite(discard_failed_expectations=False)
    return suite_name, batch_request

def run_validation():
    context = get_context()

    # Register the datasource (idempotent — safe to run every time)
    context.add_or_update_datasource(
        **{
            "name": "incidents_datasource",
            "class_name": "Datasource",
            "execution_engine": {
                "class_name": "SqlAlchemyExecutionEngine",
                "connection_string": DB_URI,
            },
            "data_connectors": {
                "default_runtime_data_connector": {
                    "class_name": "RuntimeDataConnector",
                    "batch_identifiers": ["default_identifier_name"],
                }
            },
        }
    )

    suite_name, batch_request = build_expectation_suite(context)

    checkpoint = context.add_or_update_checkpoint(
        name="incidents_checkpoint",
        validations=[
            {
                "batch_request": batch_request,
                "expectation_suite_name": suite_name,
            }
        ],
    )

    result = checkpoint.run()

    if result["success"]:
        print("✅ All validations PASSED.")
    else:
        print("❌ Some validations FAILED. See details below:")

    for validation_result in result.list_validation_results():
        for r in validation_result["results"]:
            status = "PASS" if r["success"] else "FAIL"
            print(f"[{status}] {r['expectation_config']['expectation_type']} "
                  f"on column '{r['expectation_config']['kwargs'].get('column')}'")

    return result

if __name__ == "__main__":
    run_validation()