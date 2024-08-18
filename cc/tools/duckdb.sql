CREATE SCHEMA s1;

CREATE TABLE weather (
    city    VARCHAR,
    temp_lo INTEGER, -- minimum temperature on a day
    temp_hi INTEGER, -- maximum temperature on a day
    prcp    FLOAT,
    date    DATE
);

INSERT INTO weather
VALUES ('San Francisco', 46, 50, 0.25, '1994-11-27');

COPY weather
FROM 'weather.csv';

SELECT *
FROM weather;


CREATE TABLE cities (
    name VARCHAR,
    lat  DECIMAL,
    lon  DECIMAL
);
INSERT INTO cities
VALUES ('San Francisco', -194.0, 53.0);

SELECT *
FROM weather, cities
WHERE city = name;

SELECT max(temp_lo)
FROM weather;


UPDATE weather
SET temp_hi = temp_hi - 2,  temp_lo = temp_lo - 2
WHERE date > '1994-11-28';

DELETE FROM weather
WHERE city = 'Hayward';

-- test ducklake

INSTALL ducklake;

ATTACH 'ducklake:metadata.ducklake' AS my_ducklake;
USE my_ducklake;
