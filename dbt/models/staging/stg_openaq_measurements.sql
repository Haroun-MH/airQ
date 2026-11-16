-- Staging model: expose the raw OpenAQ observations with explicit, reusable types.
-- No row is removed here; quality decisions belong in downstream models.
select
    cast(observation_id as varchar) as observation_id,
    cast(location_id as bigint) as location_id,
    cast(sensor_id as bigint) as sensor_id,
    cast(location_name as varchar) as location_name,
    cast(locality as varchar) as locality,
    cast(country_code as varchar) as country_code,
    cast(latitude as double) as latitude,
    cast(longitude as double) as longitude,
    lower(trim(cast(parameter as varchar))) as parameter,
    cast(units as varchar) as units,
    cast(value as double) as value,
    cast(measured_at as timestamptz) as measured_at,
    cast(measured_at_local as varchar) as measured_at_local,
    cast(source as varchar) as source,
    cast(ingested_at as timestamptz) as ingested_at
from {{ source('raw', 'openaq_measurements') }}
