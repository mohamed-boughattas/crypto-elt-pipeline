import dagster as dg


@dg.asset
def dbt(context: dg.AssetExecutionContext) -> dg.MaterializeResult: ...
