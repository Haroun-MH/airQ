-- Current latest measurement for each location and pollutant.
select
    location_id,
    location_name,
    locality,
    country_code,
    sensor_id,
    parameter,
    units,
    value,
    measured_at
from {{ ref('stg_openaq_measurements') }}
qualify row_number() over (
    partition by location_id, parameter
    order by measured_at desc, ingested_at desc
) = 1
