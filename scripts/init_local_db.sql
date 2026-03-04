DROP TABLE IF EXISTS orderhistoryline;
CREATE TABLE orderhistoryline (
    id BIGINT, domainid TEXT, orderhistoryid BIGINT, ean TEXT, softdeleted BOOLEAN,
    ordertype TEXT, requesteddeliverydate TEXT, confirmeddeliverydate TEXT,
    requestquantity INTEGER, requestquantitypieces INTEGER, confirmeddeliveryquantity INTEGER,
    confirmeddeliveryquantitypieces INTEGER, currencyisoalpha3 TEXT,
    unitretailprice DECIMAL(10,2), unitgrossprice DECIMAL(10,2), unitnetprice DECIMAL(10,2),
    stylenumber TEXT, status TEXT, skutype TEXT, discount DECIMAL(10,4),
    estimateddeliverydate TEXT, brandid TEXT, productlineid TEXT, note TEXT
);
COPY orderhistoryline FROM '/tmp/data.csv' DELIMITER ',' CSV HEADER;
