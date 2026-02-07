import dagster as dg


@dg.asset
def ingestion(context: dg.AssetExecutionContext) -> dg.MaterializeResult: ...
