# Liquibase Agent Report - SOL_SERVICES release 1.34

| Item | Value |
|---|---|
| Input(s) | vibehub_1.34_deploy/01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql, vibehub_1.34_deploy/02_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_BEFORE_TRIG_DDL.sql, vibehub_1.34_deploy/03_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_BEFORE_TRIG_DDL.sql, vibehub_1.34_deploy/04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql, vibehub_1.34_deploy/05_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_DDL.sql, vibehub_1.34_deploy/06_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_DDL.sql, vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql, vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql, vibehub_1.34_deploy/09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql, vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql, vibehub_1.34_deploy/11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql, vibehub_1.34_deploy/12_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql, vibehub_1.34_deploy/13_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_ALTER_DDL.sql |
| Dialect | oracle |
| Profile / author | sol_services / SOL_DATA |
| Operations analysed | 71 |
| XML changeSets | 66 (SOL_SERVICES.1.34.1.0.1 .. SOL_SERVICES.1.34.1.0.66) |
| Formatted-SQL scripts | 18 (SOL_SERVICES.1.34.1.0.1 .. SOL_SERVICES.1.34.1.0.18) |
| Overall risk | **HIGH** |
| Validation gate | **FAIL** |

## 1. Change Summary

| # | Operation | Object | What it does | Risk |
|---|---|---|---|---|
| 1 | CREATE_SEQUENCE | BILLING_EVENT.SEQ_SHADOW_ORDER_ID | Creates sequence BILLING_EVENT.SEQ_SHADOW_ORDER_ID (start 1, increment 1, NOCACHE). | LOW |
| 2 | CREATE_SEQUENCE | BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID | Creates sequence BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID (start 1, increment 1, NOCACHE). | LOW |
| 3 | CREATE_TABLE | BILLING_EVENT.SHADOW_ORDER | Creates table BILLING_EVENT.SHADOW_ORDER with 12 column(s); primary key PK_SHADOW_ORDER (SHADOW_ORDER_ID); 1 unique constraint(s) [UK_SHADOW_ORDER_COID]; foreign key(s) to BILLING_EVENT.ACCOUNT; 2 check constraint(s); tablespace BILLING_EVENT_DATA; NOLOGGING. New empty object - no impact on existing data or sessions. | MEDIUM |
| 4 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_ORDER_ACCT | Creates index BILLING_EVENT.IDX_SHADOW_ORDER_ACCT on BILLING_EVENT.SHADOW_ORDER (ACCOUNT_ID, STATUS) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 5 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_ORDER_TTL | Creates index BILLING_EVENT.IDX_SHADOW_ORDER_TTL on BILLING_EVENT.SHADOW_ORDER (STATUS, TTL_EXPIRES_AT) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 6 | COMMENT | BILLING_EVENT.SHADOW_ORDER | Sets comment on table BILLING_EVENT.SHADOW_ORDER. | - |
| 7 | COMMENT | BILLING_EVENT.SHADOW_ORDER | Sets comment on column BILLING_EVENT.SHADOW_ORDER.SHADOW_ORDER_ID. | - |
| 8 | COMMENT | BILLING_EVENT.SHADOW_ORDER | Sets comment on column BILLING_EVENT.SHADOW_ORDER.CUSTOMER_ORDER_ID. | - |
| 9 | COMMENT | BILLING_EVENT.SHADOW_ORDER | Sets comment on column BILLING_EVENT.SHADOW_ORDER.ACCOUNT_ID. | - |
| 10 | COMMENT | BILLING_EVENT.SHADOW_ORDER | Sets comment on column BILLING_EVENT.SHADOW_ORDER.ACCOUNT_NUMBER. | - |
| 11 | COMMENT | BILLING_EVENT.SHADOW_ORDER | Sets comment on column BILLING_EVENT.SHADOW_ORDER.SITE_ID. | - |
| 12 | COMMENT | BILLING_EVENT.SHADOW_ORDER | Sets comment on column BILLING_EVENT.SHADOW_ORDER.ORDER_TYPE. | - |
| 13 | COMMENT | BILLING_EVENT.SHADOW_ORDER | Sets comment on column BILLING_EVENT.SHADOW_ORDER.STATUS. | - |
| 14 | COMMENT | BILLING_EVENT.SHADOW_ORDER | Sets comment on column BILLING_EVENT.SHADOW_ORDER.TTL_EXPIRES_AT. | - |
| 15 | CREATE_TABLE | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Creates table BILLING_EVENT.SHADOW_PRODUCT_ORDER with 16 column(s); primary key PK_SHADOW_SERVICE (SHADOW_PRODUCT_ORDER_ID); 1 unique constraint(s) [UK_SHADOW_SVC_SEQ]; foreign key(s) to BILLING_EVENT.SHADOW_ORDER, BILLING_EVENT.PRODUCT; 3 check constraint(s); tablespace BILLING_EVENT_DATA; NOLOGGING. New empty object - no impact on existing data or sessions. | MEDIUM |
| 16 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_SVC_PRODUCT | Creates index BILLING_EVENT.IDX_SHADOW_SVC_PRODUCT on BILLING_EVENT.SHADOW_PRODUCT_ORDER (PRODUCT_ID) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 17 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_SVC_CATEGORY | Creates index BILLING_EVENT.IDX_SHADOW_SVC_CATEGORY on BILLING_EVENT.SHADOW_PRODUCT_ORDER (CATEGORY_CODE) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 18 | COMMENT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Sets comment on table BILLING_EVENT.SHADOW_PRODUCT_ORDER. | - |
| 19 | COMMENT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Sets comment on column BILLING_EVENT.SHADOW_PRODUCT_ORDER.SHADOW_ORDER_ID. | - |
| 20 | COMMENT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Sets comment on column BILLING_EVENT.SHADOW_PRODUCT_ORDER.PRODUCT_ID. | - |
| 21 | COMMENT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Sets comment on column BILLING_EVENT.SHADOW_PRODUCT_ORDER.CATEGORY_CODE. | - |
| 22 | COMMENT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Sets comment on column BILLING_EVENT.SHADOW_PRODUCT_ORDER.CHECKED_IN_STATUS. | - |
| 23 | COMMENT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Sets comment on column BILLING_EVENT.SHADOW_PRODUCT_ORDER.OCCURRENCE_NUMBER. | - |
| 24 | COMMENT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Sets comment on column BILLING_EVENT.SHADOW_PRODUCT_ORDER.PRODUCT_TYPE. | - |
| 25 | COMMENT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Sets comment on column BILLING_EVENT.SHADOW_PRODUCT_ORDER.CATEGORY_STATUS. | - |
| 26 | GRANT | BILLING_EVENT.SHADOW_ORDER | Grants SELECT on BILLING_EVENT.SHADOW_ORDER to BILLING_EVENT_READ_ROLE. | - |
| 27 | GRANT | BILLING_EVENT.SHADOW_ORDER | Grants SELECT, INSERT, UPDATE, DELETE on BILLING_EVENT.SHADOW_ORDER to BILLING_EVENT_WRITE_ROLE. | - |
| 28 | GRANT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Grants SELECT on BILLING_EVENT.SHADOW_PRODUCT_ORDER to BILLING_EVENT_READ_ROLE. | - |
| 29 | GRANT | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Grants SELECT, INSERT, UPDATE, DELETE on BILLING_EVENT.SHADOW_PRODUCT_ORDER to BILLING_EVENT_WRITE_ROLE. | - |
| 30 | GRANT | BILLING_EVENT.SEQ_SHADOW_ORDER_ID | Grants SELECT on BILLING_EVENT.SEQ_SHADOW_ORDER_ID to BILLING_EVENT_READ_ROLE. | - |
| 31 | GRANT | BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID | Grants SELECT on BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID to BILLING_EVENT_READ_ROLE. | - |
| 32 | CREATE_TRIGGER | BILLING_EVENT.TRG_SHADOW_ORDER_BEFORE | Creates BEFORE INSERT OR UPDATE row-level trigger BILLING_EVENT.TRG_SHADOW_ORDER_BEFORE on SHADOW_ORDER. Fires on every insert or update against SHADOW_ORDER. | MEDIUM |
| 33 | CREATE_TRIGGER | BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_BEFORE | Creates BEFORE INSERT OR UPDATE row-level trigger BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_BEFORE on SHADOW_PRODUCT_ORDER. Fires on every insert or update against SHADOW_PRODUCT_ORDER. | MEDIUM |
| 34 | CREATE_SEQUENCE | BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID | Creates sequence BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID (start 1, increment 1, NOCACHE). | LOW |
| 35 | CREATE_SEQUENCE | BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID | Creates sequence BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID (start 1, increment 1, NOCACHE). | LOW |
| 36 | CREATE_TABLE | BILLING_EVENT.SHADOW_ORDER_AUDIT | Creates table BILLING_EVENT.SHADOW_ORDER_AUDIT with 16 column(s); primary key PK_SHADOW_ORDER_AUDIT (AUDIT_ID); 1 check constraint(s); tablespace BILLING_EVENT_DATA. New empty object - no impact on existing data or sessions. | - |
| 37 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_ORDER_AUD_TS | Creates index BILLING_EVENT.IDX_SHADOW_ORDER_AUD_TS on BILLING_EVENT.SHADOW_ORDER_AUDIT (AUDIT_TIMESTAMP) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 38 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_ORDER_AUD_ID | Creates index BILLING_EVENT.IDX_SHADOW_ORDER_AUD_ID on BILLING_EVENT.SHADOW_ORDER_AUDIT (SHADOW_ORDER_ID) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 39 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_ORDER_AUD_COID | Creates index BILLING_EVENT.IDX_SHADOW_ORDER_AUD_COID on BILLING_EVENT.SHADOW_ORDER_AUDIT (CUSTOMER_ORDER_ID) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 40 | CREATE_TABLE | BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT | Creates table BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT with 20 column(s); primary key PK_SHADOW_PROD_ORDER_AUDIT (AUDIT_ID); 1 check constraint(s); tablespace BILLING_EVENT_DATA. New empty object - no impact on existing data or sessions. | - |
| 41 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_TS | Creates index BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_TS on BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT (AUDIT_TIMESTAMP) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 42 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_ID | Creates index BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_ID on BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT (SHADOW_PRODUCT_ORDER_ID) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 43 | CREATE_INDEX | BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_SOID | Creates index BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_SOID on BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT (SHADOW_ORDER_ID) in tablespace BILLING_EVENT_DATA. Table is new in this release - no lock impact. | - |
| 44 | GRANT | BILLING_EVENT.SHADOW_ORDER_AUDIT | Grants SELECT on BILLING_EVENT.SHADOW_ORDER_AUDIT to BILLING_EVENT_READ_ROLE. | - |
| 45 | GRANT | BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT | Grants SELECT on BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT to BILLING_EVENT_READ_ROLE. | - |
| 46 | GRANT | BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID | Grants SELECT on BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID to BILLING_EVENT_READ_ROLE. | - |
| 47 | GRANT | BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID | Grants SELECT on BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID to BILLING_EVENT_READ_ROLE. | - |
| 48 | CREATE_TRIGGER | BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT | Creates AFTER INSERT OR UPDATE OR DELETE row-level trigger BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT on SHADOW_ORDER. Fires on every insert or update or delete against SHADOW_ORDER. | MEDIUM |
| 49 | CREATE_TRIGGER | BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT | Creates AFTER INSERT OR UPDATE OR DELETE row-level trigger BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT on SHADOW_PRODUCT_ORDER. Fires on every insert or update or delete against SHADOW_PRODUCT_ORDER. | MEDIUM |
| 50 | DROP_CONSTRAINT | BILLING_EVENT.FK_ACCT_TRANSFER_FROM_ACCT | Drops FOREIGN KEY FK_ACCT_TRANSFER_FROM_ACCT from BILLING_EVENT.ACCOUNT_TRANSFER. | MEDIUM |
| 51 | MODIFY_COLUMN | BILLING_EVENT.ACCOUNT_TRANSFER | Modifies BILLING_EVENT.ACCOUNT_TRANSFER - FROM_ACCOUNT_ID: makes column NULLABLE. | MEDIUM |
| 52 | ADD_COLUMN | BILLING_EVENT.ACCOUNT_TRANSFER | Adds column(s) TO_ACCOUNT_ID NUMBER to BILLING_EVENT.ACCOUNT_TRANSFER. | LOW |
| 53 | UPDATE | BILLING_EVENT.ACCOUNT_TRANSFER | Updates BILLING_EVENT.ACCOUNT_TRANSFER - ALL rows. | HIGH |
| 54 | CREATE_INDEX | BILLING_EVENT.IDX_ACCOUNT_HOUSE_ADDR_ID | Creates index BILLING_EVENT.IDX_ACCOUNT_HOUSE_ADDR_ID on BILLING_EVENT.ACCOUNT (HOUSE_ADDR_ID) in tablespace BILLING_EVENT_DATA. Index build reads the whole table; DML may be blocked during the build. | MEDIUM |
| 55 | CREATE_INDEX | BILLING_EVENT.IDX_ACCT_DISC_DISCOUNT_ID | Creates index BILLING_EVENT.IDX_ACCT_DISC_DISCOUNT_ID on BILLING_EVENT.ACCOUNT_DISCOUNT (DISCOUNT_ID) in tablespace BILLING_EVENT_DATA. Index build reads the whole table; DML may be blocked during the build. | MEDIUM |
| 56 | CREATE_INDEX | BILLING_EVENT.IDX_ACCT_DISC_PRODUCT_ID | Creates index BILLING_EVENT.IDX_ACCT_DISC_PRODUCT_ID on BILLING_EVENT.ACCOUNT_DISCOUNT (DISCOUNT_PRODUCT_ID) in tablespace BILLING_EVENT_DATA. Index build reads the whole table; DML may be blocked during the build. | MEDIUM |
| 57 | CREATE_INDEX | BILLING_EVENT.IDX_ACCT_PROD_PRODUCT_ID | Creates index BILLING_EVENT.IDX_ACCT_PROD_PRODUCT_ID on BILLING_EVENT.ACCOUNT_PRODUCT (PRODUCT_ID) in tablespace BILLING_EVENT_DATA. Index build reads the whole table; DML may be blocked during the build. | MEDIUM |
| 58 | CREATE_INDEX | BILLING_EVENT.IDX_ACCT_PROD_PHONE_ACCT_ID | Creates index BILLING_EVENT.IDX_ACCT_PROD_PHONE_ACCT_ID on BILLING_EVENT.ACCOUNT_PRODUCT_PHONE (ACCOUNT_ID) in tablespace BILLING_EVENT_DATA. Index build reads the whole table; DML may be blocked during the build. | MEDIUM |
| 59 | CREATE_INDEX | BILLING_EVENT.IDX_ACCT_PROD_PHONE_PROD_ID | Creates index BILLING_EVENT.IDX_ACCT_PROD_PHONE_PROD_ID on BILLING_EVENT.ACCOUNT_PRODUCT_PHONE (ACCOUNT_PRODUCT_ID) in tablespace BILLING_EVENT_DATA. Index build reads the whole table; DML may be blocked during the build. | MEDIUM |
| 60 | CREATE_INDEX | BILLING_EVENT.IDX_BILLTO_ADDR_ACCOUNT_ID | Creates index BILLING_EVENT.IDX_BILLTO_ADDR_ACCOUNT_ID on BILLING_EVENT.BILLTO_ADDRESS (ACCOUNT_ID) in tablespace BILLING_EVENT_DATA. Index build reads the whole table; DML may be blocked during the build. | MEDIUM |
| 61 | CREATE_INDEX | BILLING_EVENT.IDX_MASTER_ACCT_MASTER_ID | Creates index BILLING_EVENT.IDX_MASTER_ACCT_MASTER_ID on BILLING_EVENT.MASTER_ACCOUNT (MASTER_ACCOUNT_ID) in tablespace BILLING_EVENT_DATA. Index build reads the whole table; DML may be blocked during the build. | MEDIUM |
| 62 | CREATE_INDEX | BILLING_EVENT.IDX_SEASONAL_ACCT_ACCOUNT_ID | Creates index BILLING_EVENT.IDX_SEASONAL_ACCT_ACCOUNT_ID on BILLING_EVENT.SEASONAL_ACCOUNT (ACCOUNT_ID) in tablespace BILLING_EVENT_DATA. Index build reads the whole table; DML may be blocked during the build. | MEDIUM |
| 63 | CREATE_VIEW | BILLING_EVENT.ACCOUNT_EVENT_VW | Replaces view BILLING_EVENT.ACCOUNT_EVENT_VW exposing 73 column(s) over BILLING_EVENT.ACCOUNT, BILLING_EVENT.HOUSE_ADDRESS, BILLING_EVENT.BILLTO_ADDRESS, BILLING_EVENT.ACCOUNT_CONTACT, BILLING_EVENT.ACCOUNT_PROD_CATEGORY, BILLING_EVENT.ACCOUNT_TRANSFER, BILLING_EVENT.SEASONAL_ACCOUNT, BILLING_EVENT.ACCOUNT_EVENT_TRANSACTION. Existing view definition is overwritten; dependent objects are invalidated and recompiled on next use. | LOW |
| 64 | COMMENT | BILLING_EVENT.ACCOUNT_EVENT_VW | Sets comment on table BILLING_EVENT.ACCOUNT_EVENT_VW. | - |
| 65 | GRANT | BILLING_EVENT.ACCOUNT_EVENT_VW | Grants SELECT on BILLING_EVENT.ACCOUNT_EVENT_VW to BILLING_EVENT_READ_ROLE. | - |
| 66 | DROP_COLUMN | BILLING_EVENT.SHADOW_ORDER | Drops column(s) STATUS from BILLING_EVENT.SHADOW_ORDER - data in these columns is permanently lost. | HIGH |
| 67 | DROP_COLUMN | BILLING_EVENT.SHADOW_PRODUCT_ORDER | Drops column(s) FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE from BILLING_EVENT.SHADOW_PRODUCT_ORDER - data in these columns is permanently lost. | HIGH |
| 68 | DROP_COLUMN | BILLING_EVENT.SHADOW_ORDER_AUDIT | Drops column(s) STATUS from BILLING_EVENT.SHADOW_ORDER_AUDIT - data in these columns is permanently lost. | HIGH |
| 69 | DROP_COLUMN | BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT | Drops column(s) FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE from BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT - data in these columns is permanently lost. | HIGH |
| 70 | CREATE_TRIGGER | BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT | Replaces AFTER INSERT OR UPDATE OR DELETE row-level trigger BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT on SHADOW_ORDER. Fires on every insert or update or delete against SHADOW_ORDER. | MEDIUM |
| 71 | CREATE_TRIGGER | BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT | Replaces AFTER INSERT OR UPDATE OR DELETE row-level trigger BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT on SHADOW_PRODUCT_ORDER. Fires on every insert or update or delete against SHADOW_PRODUCT_ORDER. | MEDIUM |

**Deploy scripts (house formatted SQL):**

| Script | changeSet | Contains |
|---|---|---|
| `01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql` | SOL_SERVICES.1.34.1.0.1 | CREATE_SEQUENCE SEQ_SHADOW_ORDER_ID, CREATE_TABLE SHADOW_ORDER, CREATE_INDEX IDX_SHADOW_ORDER_ACCT, CREATE_INDEX IDX_SHADOW_ORDER_TTL, COMMENT SHADOW_ORDER, GRANT SHADOW_ORDER, GRANT SEQ_SHADOW_ORDER_ID |
| `02_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_DDL.sql` | SOL_SERVICES.1.34.1.0.2 | CREATE_SEQUENCE SEQ_SHADOW_PRODUCT_ORDER_ID, CREATE_TABLE SHADOW_PRODUCT_ORDER, CREATE_INDEX IDX_SHADOW_SVC_PRODUCT, CREATE_INDEX IDX_SHADOW_SVC_CATEGORY, COMMENT SHADOW_PRODUCT_ORDER, GRANT SHADOW_PRODUCT_ORDER, GRANT SEQ_SHADOW_PRODUCT_ORDER_ID |
| `03_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_BEFORE_TRIG_DDL.sql` | SOL_SERVICES.1.34.1.0.3 | CREATE_TRIGGER TRG_SHADOW_ORDER_BEFORE |
| `04_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_BEFORE_TRIG_DDL.sql` | SOL_SERVICES.1.34.1.0.4 | CREATE_TRIGGER TRG_SHADOW_PRODUCT_ORDER_BEFORE |
| `05_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_DDL.sql` | SOL_SERVICES.1.34.1.0.5 | CREATE_SEQUENCE SEQ_SHADOW_ORDER_AUDIT_ID, CREATE_TABLE SHADOW_ORDER_AUDIT, CREATE_INDEX IDX_SHADOW_ORDER_AUD_TS, CREATE_INDEX IDX_SHADOW_ORDER_AUD_ID, CREATE_INDEX IDX_SHADOW_ORDER_AUD_COID, GRANT SHADOW_ORDER_AUDIT, GRANT SEQ_SHADOW_ORDER_AUDIT_ID |
| `06_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_DDL.sql` | SOL_SERVICES.1.34.1.0.6 | CREATE_SEQUENCE SEQ_SHADOW_PROD_ORDER_AUD_ID, CREATE_TABLE SHADOW_PRODUCT_ORDER_AUDIT, CREATE_INDEX IDX_SHADOW_PROD_ORD_AUD_TS, CREATE_INDEX IDX_SHADOW_PROD_ORD_AUD_ID, CREATE_INDEX IDX_SHADOW_PROD_ORD_AUD_SOID, GRANT SHADOW_PRODUCT_ORDER_AUDIT, GRANT SEQ_SHADOW_PROD_ORDER_AUD_ID |
| `07_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_DDL.sql` | SOL_SERVICES.1.34.1.0.7 | CREATE_TRIGGER TRG_SHADOW_ORDER_AUDIT |
| `08_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_DDL.sql` | SOL_SERVICES.1.34.1.0.8 | CREATE_TRIGGER TRG_SHADOW_PRODUCT_ORDER_AUDIT |
| `09_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql` | SOL_SERVICES.1.34.1.0.9 | DROP_CONSTRAINT FK_ACCT_TRANSFER_FROM_ACCT, MODIFY_COLUMN ACCOUNT_TRANSFER, ADD_COLUMN ACCOUNT_TRANSFER |
| `10_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_DML.sql` | SOL_SERVICES.1.34.1.0.10 | UPDATE ACCOUNT_TRANSFER |
| `11_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql` | SOL_SERVICES.1.34.1.0.11 | CREATE_INDEX IDX_ACCOUNT_HOUSE_ADDR_ID, CREATE_INDEX IDX_ACCT_DISC_DISCOUNT_ID, CREATE_INDEX IDX_ACCT_DISC_PRODUCT_ID, CREATE_INDEX IDX_ACCT_PROD_PRODUCT_ID, CREATE_INDEX IDX_ACCT_PROD_PHONE_ACCT_ID, CREATE_INDEX IDX_ACCT_PROD_PHONE_PROD_ID, CREATE_INDEX IDX_BILLTO_ADDR_ACCOUNT_ID, CREATE_INDEX IDX_MASTER_ACCT_MASTER_ID, CREATE_INDEX IDX_SEASONAL_ACCT_ACCOUNT_ID |
| `12_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql` | SOL_SERVICES.1.34.1.0.12 | CREATE_VIEW ACCOUNT_EVENT_VW, COMMENT ACCOUNT_EVENT_VW, GRANT ACCOUNT_EVENT_VW |
| `13_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql` | SOL_SERVICES.1.34.1.0.13 | DROP_COLUMN SHADOW_ORDER |
| `14_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_DROP_COLUMNS_ALTER_DDL.sql` | SOL_SERVICES.1.34.1.0.14 | DROP_COLUMN SHADOW_PRODUCT_ORDER |
| `15_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_DROP_COLUMNS_ALTER_DDL.sql` | SOL_SERVICES.1.34.1.0.15 | DROP_COLUMN SHADOW_ORDER_AUDIT |
| `16_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_DROP_COLUMNS_ALTER_DDL.sql` | SOL_SERVICES.1.34.1.0.16 | DROP_COLUMN SHADOW_PRODUCT_ORDER_AUDIT |
| `17_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql` | SOL_SERVICES.1.34.1.0.17 | CREATE_TRIGGER TRG_SHADOW_ORDER_AUDIT |
| `18_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_ALTER_DDL.sql` | SOL_SERVICES.1.34.1.0.18 | CREATE_TRIGGER TRG_SHADOW_PRODUCT_ORDER_AUDIT |

## 2. Liquibase XML

File: `changelog/db.changelog-SOL_SERVICES-1.34.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
    Release 1.34 - SOL_SERVICES
    Generated by liquibase-agent (offline, rule based) on 2026-10-20 11:45
    Source(s): 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql, 02_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_BEFORE_TRIG_DDL.sql, 03_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_BEFORE_TRIG_DDL.sql, 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql, 05_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_DDL.sql, 06_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_DDL.sql, 07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql, 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql, 09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql, 10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql, 11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql, 12_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql, 13_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_ALTER_DDL.sql
    Dialect  : oracle
-->
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
        http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.20.xsd">
    <preConditions onFail="HALT" onFailMessage="This changelog targets oracle only">
        <dbms type="oracle"/>
    </preConditions>

    <changeSet id="SOL_SERVICES.1.34.1.0.0-tag" author="SOL_DATA">
        <comment>Tag database before release 1.34</comment>
        <tagDatabase tag="SOL_SERVICES_1.34_PRE"/>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.1" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create sequence BILLING_EVENT.SEQ_SHADOW_ORDER_ID [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:13]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><sequenceExists sequenceName="SEQ_SHADOW_ORDER_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createSequence sequenceName="SEQ_SHADOW_ORDER_ID" schemaName="BILLING_EVENT" startValue="1" incrementBy="1" cacheSize="0" cycle="false"/>
        <rollback>
            <dropSequence sequenceName="SEQ_SHADOW_ORDER_ID" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.2" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create sequence BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:19]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><sequenceExists sequenceName="SEQ_SHADOW_PRODUCT_ORDER_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createSequence sequenceName="SEQ_SHADOW_PRODUCT_ORDER_ID" schemaName="BILLING_EVENT" startValue="1" incrementBy="1" cacheSize="0" cycle="false"/>
        <rollback>
            <dropSequence sequenceName="SEQ_SHADOW_PRODUCT_ORDER_ID" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.3" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create table BILLING_EVENT.SHADOW_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:29]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><tableExists tableName="SHADOW_ORDER" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createTable tableName="SHADOW_ORDER" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA" remarks="Shadow Selfie core order table. Holds in-flight manual orders from CBForce. References existing ACCOUNT table - no data duplication. Blocks ICOMS notification events until order completion or TTL expiry.">
            <column name="SHADOW_ORDER_ID" type="NUMBER" remarks="Primary key - MW generated">
                <constraints primaryKey="true" primaryKeyName="PK_SHADOW_ORDER" nullable="false"/>
            </column>
            <column name="CUSTOMER_ORDER_ID" type="VARCHAR2(50)" remarks="COID from CBForce - termination correlation key">
                <constraints nullable="false" unique="true" uniqueConstraintName="UK_SHADOW_ORDER_COID"/>
            </column>
            <column name="ACCOUNT_ID" type="NUMBER" remarks="Foreign key to BILLING_EVENT.ACCOUNT - references existing Selfie account">
                <constraints nullable="false"/>
            </column>
            <column name="ACCOUNT_NUMBER" type="NUMBER(9)" remarks="ICOMS account number (denormalized from ACCOUNT for lookup)">
                <constraints nullable="false"/>
            </column>
            <column name="SITE_ID" type="NUMBER(3)" remarks="ICOMS site id (denormalized from ACCOUNT for lookup)">
                <constraints nullable="false"/>
            </column>
            <column name="ORDER_TYPE" type="VARCHAR2(20)" remarks="Install, Change, or Disconnect">
                <constraints nullable="false"/>
            </column>
            <column name="STATUS" type="VARCHAR2(20)" remarks="ACTIVE, TERMINATED_COID, TERMINATED_TTL, TERMINATED_CANCEL">
                <constraints nullable="false"/>
            </column>
            <column name="TTL_EXPIRES_AT" type="TIMESTAMP WITH TIME ZONE" remarks="Shadow expiration timestamp (CREATED_DT + TTL duration)">
                <constraints nullable="false"/>
            </column>
            <column name="CREATED_DT" type="TIMESTAMP WITH TIME ZONE" defaultValueComputed="SYSTIMESTAMP">
                <constraints nullable="false"/>
            </column>
            <column name="CREATED_BY" type="VARCHAR2(30)"/>
            <column name="UPDATED_DT" type="TIMESTAMP WITH TIME ZONE" defaultValueComputed="SYSTIMESTAMP">
                <constraints nullable="false"/>
            </column>
            <column name="UPDATED_BY" type="VARCHAR2(30)"/>
        </createTable>
        <modifySql dbms="oracle">
            <append value=" NOLOGGING"/>
        </modifySql>
        <rollback>
            <dropTable tableName="SHADOW_ORDER" schemaName="BILLING_EVENT" cascadeConstraints="true"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.4" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Foreign key FK_SHADOW_ORDER_ACCOUNT on BILLING_EVENT.SHADOW_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:29]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><foreignKeyConstraintExists foreignKeyName="FK_SHADOW_ORDER_ACCOUNT"/></not>
        </preConditions>
        <addForeignKeyConstraint baseTableName="SHADOW_ORDER" baseColumnNames="ACCOUNT_ID" constraintName="FK_SHADOW_ORDER_ACCOUNT" referencedTableName="ACCOUNT" referencedColumnNames="ACCOUNT_ID" baseTableSchemaName="BILLING_EVENT" referencedTableSchemaName="BILLING_EVENT"/>
        <rollback>
            <dropForeignKeyConstraint baseTableName="SHADOW_ORDER" constraintName="FK_SHADOW_ORDER_ACCOUNT" baseTableSchemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.5" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Check constraint CHK_SHADOW_ORDER_TYPE on BILLING_EVENT.SHADOW_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:29]</comment>
        <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER ADD CONSTRAINT CHK_SHADOW_ORDER_TYPE CHECK (ORDER_TYPE IN ('Install', 'Change', 'Disconnect'))
]]></sql>
        <rollback>
            <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER DROP CONSTRAINT CHK_SHADOW_ORDER_TYPE
]]></sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.6" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Check constraint CHK_SHADOW_STATUS on BILLING_EVENT.SHADOW_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:29]</comment>
        <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER ADD CONSTRAINT CHK_SHADOW_STATUS CHECK (STATUS IN ('ACTIVE', 'TERMINATED_COID', 'TERMINATED_TTL', 'TERMINATED_CANCEL'))
]]></sql>
        <rollback>
            <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER DROP CONSTRAINT CHK_SHADOW_STATUS
]]></sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.7" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_ORDER_ACCT on SHADOW_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:54]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_ORDER_ACCT" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_ORDER_ACCT" tableName="SHADOW_ORDER" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="ACCOUNT_ID"/>
            <column name="STATUS"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_ORDER_ACCT" tableName="SHADOW_ORDER" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.8" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_ORDER_TTL on SHADOW_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:55]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_ORDER_TTL" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_ORDER_TTL" tableName="SHADOW_ORDER" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="STATUS"/>
            <column name="TTL_EXPIRES_AT"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_ORDER_TTL" tableName="SHADOW_ORDER" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.9" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create table BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:72]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><tableExists tableName="SHADOW_PRODUCT_ORDER" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createTable tableName="SHADOW_PRODUCT_ORDER" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA" remarks="Individual ICOMS service codes from CBForce order. CBForce already sends ICOMS codes (RDM-compatible) - no SKU translation needed.">
            <column name="SHADOW_PRODUCT_ORDER_ID" type="NUMBER">
                <constraints primaryKey="true" primaryKeyName="PK_SHADOW_SERVICE" nullable="false"/>
            </column>
            <column name="SHADOW_ORDER_ID" type="NUMBER" remarks="Foreign key to SHADOW_ORDER">
                <constraints nullable="false"/>
            </column>
            <column name="PRODUCT_ID" type="NUMBER" remarks="Foreign key to PRODUCT reference table">
                <constraints nullable="false"/>
            </column>
            <column name="PAID_QUANTITY" type="NUMBER(5)" defaultValueNumeric="1"/>
            <column name="FREE_QUANTITY" type="NUMBER(5)" defaultValueNumeric="0"/>
            <column name="CHECKED_IN_STATUS" type="VARCHAR2(1)" defaultValue="I" remarks="I=Install Pending (always for shadow), A=Active, D=Disconnect Pending"/>
            <column name="OCCURRENCE_NUMBER" type="NUMBER(10)" remarks="Synthesized monotonic sequence. Real ICOMS occurrence assigned when order completes."/>
            <column name="PRODUCT_TYPE" type="VARCHAR2(1)" remarks="R=Recurring, T=Temporary (from catalog)"/>
            <column name="PRODUCT_SEQUENCE" type="NUMBER(5)"/>
            <column name="CATEGORY_CODE" type="VARCHAR2(1)" remarks="LOB type: C=Video, T=Telephony, D=Data, W=Wireless, H=Security, S=Special, L=Line Card, M=Mobile"/>
            <column name="CATEGORY_STATUS" type="VARCHAR2(1)" defaultValue="2" remarks="2 = Pending Connect (always for shadow orders)"/>
            <column name="CATEGORY_SEQUENCE" type="NUMBER(3)"/>
            <column name="CREATED_DT" type="TIMESTAMP WITH TIME ZONE" defaultValueComputed="SYSTIMESTAMP">
                <constraints nullable="false"/>
            </column>
            <column name="CREATED_BY" type="VARCHAR2(30)">
                <constraints nullable="false"/>
            </column>
            <column name="UPDATED_DT" type="TIMESTAMP WITH TIME ZONE" defaultValueComputed="SYSTIMESTAMP">
                <constraints nullable="false"/>
            </column>
            <column name="UPDATED_BY" type="VARCHAR2(30)">
                <constraints nullable="false"/>
            </column>
        </createTable>
        <modifySql dbms="oracle">
            <append value=" NOLOGGING"/>
        </modifySql>
        <rollback>
            <dropTable tableName="SHADOW_PRODUCT_ORDER" schemaName="BILLING_EVENT" cascadeConstraints="true"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.10" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Foreign key FK_SHADOW_SVC_ORDER on BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:72]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><foreignKeyConstraintExists foreignKeyName="FK_SHADOW_SVC_ORDER"/></not>
        </preConditions>
        <addForeignKeyConstraint baseTableName="SHADOW_PRODUCT_ORDER" baseColumnNames="SHADOW_ORDER_ID" constraintName="FK_SHADOW_SVC_ORDER" referencedTableName="SHADOW_ORDER" referencedColumnNames="SHADOW_ORDER_ID" baseTableSchemaName="BILLING_EVENT" referencedTableSchemaName="BILLING_EVENT" onDelete="CASCADE"/>
        <rollback>
            <dropForeignKeyConstraint baseTableName="SHADOW_PRODUCT_ORDER" constraintName="FK_SHADOW_SVC_ORDER" baseTableSchemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.11" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Foreign key FK_SHADOW_SVC_PRODUCT on BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:72]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><foreignKeyConstraintExists foreignKeyName="FK_SHADOW_SVC_PRODUCT"/></not>
        </preConditions>
        <addForeignKeyConstraint baseTableName="SHADOW_PRODUCT_ORDER" baseColumnNames="PRODUCT_ID" constraintName="FK_SHADOW_SVC_PRODUCT" referencedTableName="PRODUCT" referencedColumnNames="PRODUCT_ID" baseTableSchemaName="BILLING_EVENT" referencedTableSchemaName="BILLING_EVENT"/>
        <rollback>
            <dropForeignKeyConstraint baseTableName="SHADOW_PRODUCT_ORDER" constraintName="FK_SHADOW_SVC_PRODUCT" baseTableSchemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.12" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Unique constraint UK_SHADOW_SVC_SEQ on BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:72]</comment>
        <addUniqueConstraint tableName="SHADOW_PRODUCT_ORDER" schemaName="BILLING_EVENT" columnNames="SHADOW_ORDER_ID, PRODUCT_SEQUENCE" constraintName="UK_SHADOW_SVC_SEQ" tablespace="BILLING_EVENT_DATA"/>
        <rollback>
            <dropUniqueConstraint tableName="SHADOW_PRODUCT_ORDER" schemaName="BILLING_EVENT" constraintName="UK_SHADOW_SVC_SEQ"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.13" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Check constraint CHK_SHADOW_SVC_TYPE on BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:72]</comment>
        <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD CONSTRAINT CHK_SHADOW_SVC_TYPE CHECK (PRODUCT_TYPE IN ('R', 'T'))
]]></sql>
        <rollback>
            <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER DROP CONSTRAINT CHK_SHADOW_SVC_TYPE
]]></sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.14" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Check constraint CHK_SHADOW_CHECKED_IN on BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:72]</comment>
        <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD CONSTRAINT CHK_SHADOW_CHECKED_IN CHECK (CHECKED_IN_STATUS IN ('I', 'A', 'D'))
]]></sql>
        <rollback>
            <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER DROP CONSTRAINT CHK_SHADOW_CHECKED_IN
]]></sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.15" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Check constraint CHK_SHADOW_CATEGORY on BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:72]</comment>
        <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD CONSTRAINT CHK_SHADOW_CATEGORY CHECK (CATEGORY_CODE IN ('C', 'T', 'D', 'W', 'H', 'S', 'L', 'M'))
]]></sql>
        <rollback>
            <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER DROP CONSTRAINT CHK_SHADOW_CATEGORY
]]></sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.16" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_SVC_PRODUCT on SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:105]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_SVC_PRODUCT" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_SVC_PRODUCT" tableName="SHADOW_PRODUCT_ORDER" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="PRODUCT_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_SVC_PRODUCT" tableName="SHADOW_PRODUCT_ORDER" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.17" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_SVC_CATEGORY on SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:106]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_SVC_CATEGORY" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_SVC_CATEGORY" tableName="SHADOW_PRODUCT_ORDER" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="CATEGORY_CODE"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_SVC_CATEGORY" tableName="SHADOW_PRODUCT_ORDER" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.18" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SHADOW_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:123]</comment>
        <sql><![CDATA[
GRANT SELECT ON "BILLING_EVENT"."SHADOW_ORDER" TO "BILLING_EVENT_READ_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT ON BILLING_EVENT.SHADOW_ORDER FROM BILLING_EVENT_READ_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.19" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SHADOW_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:124]</comment>
        <sql><![CDATA[
GRANT SELECT, INSERT, UPDATE, DELETE ON "BILLING_EVENT"."SHADOW_ORDER" TO "BILLING_EVENT_WRITE_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT, INSERT, UPDATE, DELETE ON BILLING_EVENT.SHADOW_ORDER FROM BILLING_EVENT_WRITE_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.20" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:127]</comment>
        <sql><![CDATA[
GRANT SELECT ON "BILLING_EVENT"."SHADOW_PRODUCT_ORDER" TO "BILLING_EVENT_READ_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT ON BILLING_EVENT.SHADOW_PRODUCT_ORDER FROM BILLING_EVENT_READ_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.21" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:128]</comment>
        <sql><![CDATA[
GRANT SELECT, INSERT, UPDATE, DELETE ON "BILLING_EVENT"."SHADOW_PRODUCT_ORDER" TO "BILLING_EVENT_WRITE_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT, INSERT, UPDATE, DELETE ON BILLING_EVENT.SHADOW_PRODUCT_ORDER FROM BILLING_EVENT_WRITE_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.22" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SEQ_SHADOW_ORDER_ID [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:133]</comment>
        <sql><![CDATA[
GRANT SELECT ON "BILLING_EVENT"."SEQ_SHADOW_ORDER_ID" TO "BILLING_EVENT_READ_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT ON BILLING_EVENT.SEQ_SHADOW_ORDER_ID FROM BILLING_EVENT_READ_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.23" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID [source 01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:134]</comment>
        <sql><![CDATA[
GRANT SELECT ON "BILLING_EVENT"."SEQ_SHADOW_PRODUCT_ORDER_ID" TO "BILLING_EVENT_READ_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT ON BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID FROM BILLING_EVENT_READ_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.24" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create or replace trigger BILLING_EVENT.TRG_SHADOW_ORDER_BEFORE [source 02_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_BEFORE_TRIG_DDL.sql:11]</comment>
        <sql splitStatements="false" stripComments="false"><![CDATA[
CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_BEFORE
BEFORE INSERT OR UPDATE ON BILLING_EVENT.SHADOW_ORDER
FOR EACH ROW
DECLARE
    v_username VARCHAR2(128);
BEGIN
    SELECT SYS_CONTEXT('USERENV', 'SESSION_USER')
      INTO v_username
      FROM DUAL;

    IF INSERTING THEN
        :NEW.CREATED_DT := CURRENT_TIMESTAMP;
        :NEW.CREATED_BY := v_username;
    END IF;

    :NEW.UPDATED_DT := CURRENT_TIMESTAMP;
    :NEW.UPDATED_BY := v_username;
END;
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
DROP TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_BEFORE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.25" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create or replace trigger BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_BEFORE [source 03_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_BEFORE_TRIG_DDL.sql:11]</comment>
        <sql splitStatements="false" stripComments="false"><![CDATA[
CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_BEFORE
BEFORE INSERT OR UPDATE ON BILLING_EVENT.SHADOW_PRODUCT_ORDER
FOR EACH ROW
DECLARE
    v_username VARCHAR2(128);
BEGIN
    SELECT SYS_CONTEXT('USERENV', 'SESSION_USER')
      INTO v_username
      FROM DUAL;

    IF INSERTING THEN
        :NEW.CREATED_DT := CURRENT_TIMESTAMP;
        :NEW.CREATED_BY := v_username;
    END IF;

    :NEW.UPDATED_DT := CURRENT_TIMESTAMP;
    :NEW.UPDATED_BY := v_username;
END;
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
DROP TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_BEFORE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.26" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create sequence BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:13]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><sequenceExists sequenceName="SEQ_SHADOW_ORDER_AUDIT_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createSequence sequenceName="SEQ_SHADOW_ORDER_AUDIT_ID" schemaName="BILLING_EVENT" startValue="1" incrementBy="1" cacheSize="0" cycle="false"/>
        <rollback>
            <dropSequence sequenceName="SEQ_SHADOW_ORDER_AUDIT_ID" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.27" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create sequence BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:19]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><sequenceExists sequenceName="SEQ_SHADOW_PROD_ORDER_AUD_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createSequence sequenceName="SEQ_SHADOW_PROD_ORDER_AUD_ID" schemaName="BILLING_EVENT" startValue="1" incrementBy="1" cacheSize="0" cycle="false"/>
        <rollback>
            <dropSequence sequenceName="SEQ_SHADOW_PROD_ORDER_AUD_ID" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.28" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create table BILLING_EVENT.SHADOW_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:28]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><tableExists tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createTable tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="AUDIT_ID" type="NUMBER">
                <constraints primaryKey="true" primaryKeyName="PK_SHADOW_ORDER_AUDIT" nullable="false"/>
            </column>
            <column name="AUDIT_TIMESTAMP" type="TIMESTAMP WITH TIME ZONE" defaultValueComputed="SYSTIMESTAMP">
                <constraints nullable="false"/>
            </column>
            <column name="AUDIT_ACTION" type="VARCHAR2(10)">
                <constraints nullable="false"/>
            </column>
            <column name="AUDIT_TRANSACTION_ID" type="VARCHAR2(100)"/>
            <column name="SHADOW_ORDER_ID" type="NUMBER"/>
            <column name="CUSTOMER_ORDER_ID" type="VARCHAR2(50)"/>
            <column name="ACCOUNT_ID" type="NUMBER"/>
            <column name="ACCOUNT_NUMBER" type="NUMBER(9)"/>
            <column name="SITE_ID" type="NUMBER(3)"/>
            <column name="ORDER_TYPE" type="VARCHAR2(20)"/>
            <column name="STATUS" type="VARCHAR2(20)"/>
            <column name="TTL_EXPIRES_AT" type="TIMESTAMP WITH TIME ZONE"/>
            <column name="CREATED_DT" type="TIMESTAMP WITH TIME ZONE"/>
            <column name="CREATED_BY" type="VARCHAR2(30)"/>
            <column name="UPDATED_DT" type="TIMESTAMP WITH TIME ZONE"/>
            <column name="UPDATED_BY" type="VARCHAR2(30)"/>
        </createTable>
        <rollback>
            <dropTable tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT" cascadeConstraints="true"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.29" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Check constraint CHK_SHADOW_ORDER_AUD_ACT on BILLING_EVENT.SHADOW_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:28]</comment>
        <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER_AUDIT ADD CONSTRAINT CHK_SHADOW_ORDER_AUD_ACT CHECK (AUDIT_ACTION IN ('INSERT', 'UPDATE', 'DELETE'))
]]></sql>
        <rollback>
            <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER_AUDIT DROP CONSTRAINT CHK_SHADOW_ORDER_AUD_ACT
]]></sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.30" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_ORDER_AUD_TS on SHADOW_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:50]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_ORDER_AUD_TS" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_ORDER_AUD_TS" tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="AUDIT_TIMESTAMP"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_ORDER_AUD_TS" tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.31" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_ORDER_AUD_ID on SHADOW_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:51]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_ORDER_AUD_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_ORDER_AUD_ID" tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="SHADOW_ORDER_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_ORDER_AUD_ID" tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.32" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_ORDER_AUD_COID on SHADOW_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:52]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_ORDER_AUD_COID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_ORDER_AUD_COID" tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="CUSTOMER_ORDER_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_ORDER_AUD_COID" tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.33" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create table BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:57]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><tableExists tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createTable tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="AUDIT_ID" type="NUMBER">
                <constraints primaryKey="true" primaryKeyName="PK_SHADOW_PROD_ORDER_AUDIT" nullable="false"/>
            </column>
            <column name="AUDIT_TIMESTAMP" type="TIMESTAMP WITH TIME ZONE" defaultValueComputed="SYSTIMESTAMP">
                <constraints nullable="false"/>
            </column>
            <column name="AUDIT_ACTION" type="VARCHAR2(10)">
                <constraints nullable="false"/>
            </column>
            <column name="AUDIT_TRANSACTION_ID" type="VARCHAR2(100)"/>
            <column name="SHADOW_PRODUCT_ORDER_ID" type="NUMBER"/>
            <column name="SHADOW_ORDER_ID" type="NUMBER"/>
            <column name="PRODUCT_ID" type="NUMBER"/>
            <column name="PAID_QUANTITY" type="NUMBER(5)"/>
            <column name="FREE_QUANTITY" type="NUMBER(5)"/>
            <column name="CHECKED_IN_STATUS" type="VARCHAR2(1)"/>
            <column name="OCCURRENCE_NUMBER" type="NUMBER(10)"/>
            <column name="PRODUCT_TYPE" type="VARCHAR2(1)"/>
            <column name="PRODUCT_SEQUENCE" type="NUMBER(5)"/>
            <column name="CATEGORY_CODE" type="VARCHAR2(1)"/>
            <column name="CATEGORY_STATUS" type="VARCHAR2(1)"/>
            <column name="CATEGORY_SEQUENCE" type="NUMBER(3)"/>
            <column name="CREATED_DT" type="TIMESTAMP WITH TIME ZONE"/>
            <column name="CREATED_BY" type="VARCHAR2(30)"/>
            <column name="UPDATED_DT" type="TIMESTAMP WITH TIME ZONE"/>
            <column name="UPDATED_BY" type="VARCHAR2(30)"/>
        </createTable>
        <rollback>
            <dropTable tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT" cascadeConstraints="true"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.34" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Check constraint CHK_SHADOW_PROD_ORD_AUD_ACT on BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:57]</comment>
        <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT ADD CONSTRAINT CHK_SHADOW_PROD_ORD_AUD_ACT CHECK (AUDIT_ACTION IN ('INSERT', 'UPDATE', 'DELETE'))
]]></sql>
        <rollback>
            <sql><![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT DROP CONSTRAINT CHK_SHADOW_PROD_ORD_AUD_ACT
]]></sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.35" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_PROD_ORD_AUD_TS on SHADOW_PRODUCT_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:83]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_PROD_ORD_AUD_TS" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_PROD_ORD_AUD_TS" tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="AUDIT_TIMESTAMP"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_PROD_ORD_AUD_TS" tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.36" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_PROD_ORD_AUD_ID on SHADOW_PRODUCT_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:84]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_PROD_ORD_AUD_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_PROD_ORD_AUD_ID" tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="SHADOW_PRODUCT_ORDER_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_PROD_ORD_AUD_ID" tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.37" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SHADOW_PROD_ORD_AUD_SOID on SHADOW_PRODUCT_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:85]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SHADOW_PROD_ORD_AUD_SOID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SHADOW_PROD_ORD_AUD_SOID" tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="SHADOW_ORDER_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SHADOW_PROD_ORD_AUD_SOID" tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.38" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SHADOW_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:92]</comment>
        <sql><![CDATA[
GRANT SELECT ON "BILLING_EVENT"."SHADOW_ORDER_AUDIT" TO "BILLING_EVENT_READ_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT ON BILLING_EVENT.SHADOW_ORDER_AUDIT FROM BILLING_EVENT_READ_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.39" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:95]</comment>
        <sql><![CDATA[
GRANT SELECT ON "BILLING_EVENT"."SHADOW_PRODUCT_ORDER_AUDIT" TO "BILLING_EVENT_READ_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT ON BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT FROM BILLING_EVENT_READ_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.40" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:100]</comment>
        <sql><![CDATA[
GRANT SELECT ON "BILLING_EVENT"."SEQ_SHADOW_ORDER_AUDIT_ID" TO "BILLING_EVENT_READ_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT ON BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID FROM BILLING_EVENT_READ_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.41" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID [source 04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:101]</comment>
        <sql><![CDATA[
GRANT SELECT ON "BILLING_EVENT"."SEQ_SHADOW_PROD_ORDER_AUD_ID" TO "BILLING_EVENT_READ_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT ON BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID FROM BILLING_EVENT_READ_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.42" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create or replace trigger BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT [source 05_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_DDL.sql:11]</comment>
        <sql splitStatements="false" stripComments="false"><![CDATA[
CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
AFTER INSERT OR UPDATE OR DELETE ON BILLING_EVENT.SHADOW_ORDER
FOR EACH ROW
DECLARE
    v_action VARCHAR2(10);
    v_transaction_id VARCHAR2(100);
BEGIN
    IF INSERTING THEN
        v_action := 'INSERT';
    ELSIF UPDATING THEN
        v_action := 'UPDATE';
    ELSIF DELETING THEN
        v_action := 'DELETE';
    END IF;

    v_transaction_id := SYS_GUID();

    INSERT INTO BILLING_EVENT.SHADOW_ORDER_AUDIT (
        AUDIT_ID,
        AUDIT_TIMESTAMP,
        AUDIT_ACTION,
        AUDIT_TRANSACTION_ID,
        SHADOW_ORDER_ID,
        CUSTOMER_ORDER_ID,
        ACCOUNT_ID,
        ACCOUNT_NUMBER,
        SITE_ID,
        ORDER_TYPE,
        STATUS,
        TTL_EXPIRES_AT,
        CREATED_DT,
        CREATED_BY,
        UPDATED_DT,
        UPDATED_BY
    ) VALUES (
        BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID.NEXTVAL,
        SYSTIMESTAMP,
        v_action,
        v_transaction_id,
        COALESCE(:NEW.SHADOW_ORDER_ID, :OLD.SHADOW_ORDER_ID),
        COALESCE(:NEW.CUSTOMER_ORDER_ID, :OLD.CUSTOMER_ORDER_ID),
        COALESCE(:NEW.ACCOUNT_ID, :OLD.ACCOUNT_ID),
        COALESCE(:NEW.ACCOUNT_NUMBER, :OLD.ACCOUNT_NUMBER),
        COALESCE(:NEW.SITE_ID, :OLD.SITE_ID),
        COALESCE(:NEW.ORDER_TYPE, :OLD.ORDER_TYPE),
        COALESCE(:NEW.STATUS, :OLD.STATUS),
        COALESCE(:NEW.TTL_EXPIRES_AT, :OLD.TTL_EXPIRES_AT),
        COALESCE(:NEW.CREATED_DT, :OLD.CREATED_DT),
        COALESCE(:NEW.CREATED_BY, :OLD.CREATED_BY),
        COALESCE(:NEW.UPDATED_DT, :OLD.UPDATED_DT),
        COALESCE(:NEW.UPDATED_BY, :OLD.UPDATED_BY)
    );
END;
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
DROP TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.43" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create or replace trigger BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT [source 06_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_DDL.sql:11]</comment>
        <sql splitStatements="false" stripComments="false"><![CDATA[
CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT
AFTER INSERT OR UPDATE OR DELETE ON BILLING_EVENT.SHADOW_PRODUCT_ORDER
FOR EACH ROW
DECLARE
    v_action VARCHAR2(10);
    v_transaction_id VARCHAR2(100);
BEGIN
    IF INSERTING THEN
        v_action := 'INSERT';
    ELSIF UPDATING THEN
        v_action := 'UPDATE';
    ELSIF DELETING THEN
        v_action := 'DELETE';
    END IF;

    v_transaction_id := SYS_GUID();

    INSERT INTO BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT (
        AUDIT_ID,
        AUDIT_TIMESTAMP,
        AUDIT_ACTION,
        AUDIT_TRANSACTION_ID,
        SHADOW_PRODUCT_ORDER_ID,
        SHADOW_ORDER_ID,
        PRODUCT_ID,
        PAID_QUANTITY,
        FREE_QUANTITY,
        CHECKED_IN_STATUS,
        OCCURRENCE_NUMBER,
        PRODUCT_TYPE,
        PRODUCT_SEQUENCE,
        CATEGORY_CODE,
        CATEGORY_STATUS,
        CATEGORY_SEQUENCE,
        CREATED_DT,
        CREATED_BY,
        UPDATED_DT,
        UPDATED_BY
    ) VALUES (
        BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID.NEXTVAL,
        SYSTIMESTAMP,
        v_action,
        v_transaction_id,
        COALESCE(:NEW.SHADOW_PRODUCT_ORDER_ID, :OLD.SHADOW_PRODUCT_ORDER_ID),
        COALESCE(:NEW.SHADOW_ORDER_ID, :OLD.SHADOW_ORDER_ID),
        COALESCE(:NEW.PRODUCT_ID, :OLD.PRODUCT_ID),
        COALESCE(:NEW.PAID_QUANTITY, :OLD.PAID_QUANTITY),
        COALESCE(:NEW.FREE_QUANTITY, :OLD.FREE_QUANTITY),
        COALESCE(:NEW.CHECKED_IN_STATUS, :OLD.CHECKED_IN_STATUS),
        COALESCE(:NEW.OCCURRENCE_NUMBER, :OLD.OCCURRENCE_NUMBER),
        COALESCE(:NEW.PRODUCT_TYPE, :OLD.PRODUCT_TYPE),
        COALESCE(:NEW.PRODUCT_SEQUENCE, :OLD.PRODUCT_SEQUENCE),
        COALESCE(:NEW.CATEGORY_CODE, :OLD.CATEGORY_CODE),
        COALESCE(:NEW.CATEGORY_STATUS, :OLD.CATEGORY_STATUS),
        COALESCE(:NEW.CATEGORY_SEQUENCE, :OLD.CATEGORY_SEQUENCE),
        COALESCE(:NEW.CREATED_DT, :OLD.CREATED_DT),
        COALESCE(:NEW.CREATED_BY, :OLD.CREATED_BY),
        COALESCE(:NEW.UPDATED_DT, :OLD.UPDATED_DT),
        COALESCE(:NEW.UPDATED_BY, :OLD.UPDATED_BY)
    );
END;
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
DROP TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.44" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Drop FK FK_ACCT_TRANSFER_FROM_ACCT on BILLING_EVENT.ACCOUNT_TRANSFER [source 07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:11]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <foreignKeyConstraintExists foreignKeyName="FK_ACCT_TRANSFER_FROM_ACCT"/>
        </preConditions>
        <dropForeignKeyConstraint baseTableName="ACCOUNT_TRANSFER" constraintName="FK_ACCT_TRANSFER_FROM_ACCT" baseTableSchemaName="BILLING_EVENT"/>
        <rollback>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.ACCOUNT_TRANSFER ADD CONSTRAINT FK_ACCT_TRANSFER_FROM_ACCT FOREIGN KEY (FROM_ACCOUNT_ID) REFERENCES BILLING_EVENT.ACCOUNT (ACCOUNT_ID)
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.45" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Modify column(s) on BILLING_EVENT.ACCOUNT_TRANSFER [source 07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:14]</comment>
        <dropNotNullConstraint tableName="ACCOUNT_TRANSFER" schemaName="BILLING_EVENT" columnName="FROM_ACCOUNT_ID"/>
        <rollback>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.ACCOUNT_TRANSFER MODIFY (FROM_ACCOUNT_ID NOT NULL)
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.46" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Add column(s) to BILLING_EVENT.ACCOUNT_TRANSFER [source 07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:17]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><columnExists tableName="ACCOUNT_TRANSFER" columnName="TO_ACCOUNT_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <addColumn tableName="ACCOUNT_TRANSFER" schemaName="BILLING_EVENT">
            <column name="TO_ACCOUNT_ID" type="NUMBER"/>
        </addColumn>
        <rollback>
            <dropColumn tableName="ACCOUNT_TRANSFER" schemaName="BILLING_EVENT">
                <column name="TO_ACCOUNT_ID"/>
            </dropColumn>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.47" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Backup rows of BILLING_EVENT.ACCOUNT_TRANSFER before update [source 07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:20]</comment>
        <sql><![CDATA[
CREATE TABLE BILLING_EVENT.ACCOUNT_TRANSFER_BKP53 AS SELECT * FROM BILLING_EVENT.ACCOUNT_TRANSFER
]]></sql>
        <rollback>
            <sql><![CDATA[
DROP TABLE BILLING_EVENT.ACCOUNT_TRANSFER_BKP53
]]></sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.48" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Data: update BILLING_EVENT.ACCOUNT_TRANSFER [source 07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:20]</comment>
        <sql><![CDATA[
UPDATE "BILLING_EVENT"."ACCOUNT_TRANSFER"
SET TO_ACCOUNT_ID = ACCOUNT_ID
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
MERGE INTO BILLING_EVENT.ACCOUNT_TRANSFER t USING BILLING_EVENT.ACCOUNT_TRANSFER_BKP53 b ON (t.ACCOUNT_TRANSFER_ID = b.ACCOUNT_TRANSFER_ID) WHEN MATCHED THEN UPDATE SET t.TO_ACCOUNT_ID = b.TO_ACCOUNT_ID
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.49" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_ACCOUNT_HOUSE_ADDR_ID on ACCOUNT [source 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:16]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_ACCOUNT_HOUSE_ADDR_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_ACCOUNT_HOUSE_ADDR_ID" tableName="ACCOUNT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="HOUSE_ADDR_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_ACCOUNT_HOUSE_ADDR_ID" tableName="ACCOUNT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.50" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_ACCT_DISC_DISCOUNT_ID on ACCOUNT_DISCOUNT [source 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:25]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_ACCT_DISC_DISCOUNT_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_ACCT_DISC_DISCOUNT_ID" tableName="ACCOUNT_DISCOUNT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="DISCOUNT_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_ACCT_DISC_DISCOUNT_ID" tableName="ACCOUNT_DISCOUNT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.51" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_ACCT_DISC_PRODUCT_ID on ACCOUNT_DISCOUNT [source 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:34]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_ACCT_DISC_PRODUCT_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_ACCT_DISC_PRODUCT_ID" tableName="ACCOUNT_DISCOUNT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="DISCOUNT_PRODUCT_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_ACCT_DISC_PRODUCT_ID" tableName="ACCOUNT_DISCOUNT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.52" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_ACCT_PROD_PRODUCT_ID on ACCOUNT_PRODUCT [source 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:43]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_ACCT_PROD_PRODUCT_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_ACCT_PROD_PRODUCT_ID" tableName="ACCOUNT_PRODUCT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="PRODUCT_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_ACCT_PROD_PRODUCT_ID" tableName="ACCOUNT_PRODUCT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.53" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_ACCT_PROD_PHONE_ACCT_ID on ACCOUNT_PRODUCT_PHONE [source 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:52]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_ACCT_PROD_PHONE_ACCT_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_ACCT_PROD_PHONE_ACCT_ID" tableName="ACCOUNT_PRODUCT_PHONE" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="ACCOUNT_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_ACCT_PROD_PHONE_ACCT_ID" tableName="ACCOUNT_PRODUCT_PHONE" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.54" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_ACCT_PROD_PHONE_PROD_ID on ACCOUNT_PRODUCT_PHONE [source 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:61]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_ACCT_PROD_PHONE_PROD_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_ACCT_PROD_PHONE_PROD_ID" tableName="ACCOUNT_PRODUCT_PHONE" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="ACCOUNT_PRODUCT_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_ACCT_PROD_PHONE_PROD_ID" tableName="ACCOUNT_PRODUCT_PHONE" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.55" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_BILLTO_ADDR_ACCOUNT_ID on BILLTO_ADDRESS [source 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:70]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_BILLTO_ADDR_ACCOUNT_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_BILLTO_ADDR_ACCOUNT_ID" tableName="BILLTO_ADDRESS" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="ACCOUNT_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_BILLTO_ADDR_ACCOUNT_ID" tableName="BILLTO_ADDRESS" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.56" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_MASTER_ACCT_MASTER_ID on MASTER_ACCOUNT [source 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:79]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_MASTER_ACCT_MASTER_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_MASTER_ACCT_MASTER_ID" tableName="MASTER_ACCOUNT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="MASTER_ACCOUNT_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_MASTER_ACCT_MASTER_ID" tableName="MASTER_ACCOUNT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.57" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create index IDX_SEASONAL_ACCT_ACCOUNT_ID on SEASONAL_ACCOUNT [source 08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:88]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <not><indexExists indexName="IDX_SEASONAL_ACCT_ACCOUNT_ID" schemaName="BILLING_EVENT"/></not>
        </preConditions>
        <createIndex indexName="IDX_SEASONAL_ACCT_ACCOUNT_ID" tableName="SEASONAL_ACCOUNT" schemaName="BILLING_EVENT" tablespace="BILLING_EVENT_DATA">
            <column name="ACCOUNT_ID"/>
        </createIndex>
        <rollback>
            <dropIndex indexName="IDX_SEASONAL_ACCT_ACCOUNT_ID" tableName="SEASONAL_ACCOUNT" schemaName="BILLING_EVENT"/>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.58" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create or replace view BILLING_EVENT.ACCOUNT_EVENT_VW [source 09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql:18]</comment>
        <sql splitStatements="false" stripComments="false"><![CDATA[
CREATE OR REPLACE FORCE EDITIONABLE VIEW "BILLING_EVENT"."ACCOUNT_EVENT_VW" ("ACCOUNT_ID", "SITE_ID", "ACCOUNT_NUMBER", "TWELVE_DIGIT_NUMBER", "THIRTEEN_DIGIT_NUMBER", "SIXTEEN_DIGIT_NUMBER", "COMPANY", "DIVISION", "FRANCHISE_NUMBER", "FIRST_NAME", "LAST_NAME", "BUSINESS_NAME", "BILLING_STATUS", "ACCOUNT_STATUS", "SECURITY_CODE", "BILL_TYPE", "DELINQUENCY_STATUS", "BIRTH_DATE", "TAX_TYPE", "TAX_IDENTIFIER", "DRIVERS_LICENSE_NUM", "PERSISTENT_ID", "CONTROLLER_ID", "VCM", "INSTALL_DATE", "DISCONNECTED_DATE", "CUSTOMER_CATEGORY", "CUSTOMER_TYPE", "SERVICE_ADDR_LINE1", "SERVICE_ADDR_LINE2", "SERVICE_CITY", "SERVICE_STATE", "SERVICE_ZIP5", "SERVICE_ZIP4", "NODE_NUMBER", "HOUSE_NUMBER", "HOUSE_DEVELOPMENT_NUMBER", "BILLTO_ADDR_LINE1", "BILLTO_ADDR_LINE2", "BILLTO_CITY", "BILLTO_STATE", "BILLTO_ZIP5", "BILLTO_ZIP4", "BILLTO_CUSTOMER_NAME", "BILLTO_BUSINESS_NAME", "ACCOUNT_CONTACT_ID", "NOTIFICATION_METHOD", "CONTACT_TYPE", "CONTACT_VALUE", "PRIMARY_CONTACT", "OPT_IN_FLAG", "ACCOUNT_PROD_CATEGORY_ID", "PROD_CATEGORY_CODE", "CUST_PROD_CAT_STATUS", "CUST_PROD_CAT_STATUS_DATE", "TO_ACCOUNT_ID", "FROM_ACCOUNT_ID", "TRANSFER_STATUS", "SEASONAL_SUSPEND_START", "SEASONAL_SUSPEND_END", "AUTH_USER", "MASTER_ACCOUNT", "TRANSACTION_ID", "EVENT_TIMESTAMP", "EVENT_ID", "CORRELATION_ID", "ORIGIN", "SYNC_STATUS", "ERR_MSG", "ACCOUNT_CREATED_DT", "ACCOUNT_CREATED_BY", "ACCOUNT_UPDATED_DT", "ACCOUNT_UPDATED_BY") AS
  SELECT
    a.ACCOUNT_ID,
    a.SITE_ID,
    a.ACCOUNT_NUMBER,
    LPAD(a.SITE_ID, 3, '0') || LPAD(a.ACCOUNT_NUMBER, 9, '0') AS TWELVE_DIGIT_NUMBER,
    LPAD(a.COMPANY, 2, '0') || LPAD(a.DIVISION, 2, '0') || LPAD(a.ACCOUNT_NUMBER, 9, '0') AS THIRTEEN_DIGIT_NUMBER,
    LPAD(a.SITE_ID, 3, '0') || LPAD(a.COMPANY, 2, '0') || LPAD(a.DIVISION, 2, '0') || LPAD(a.ACCOUNT_NUMBER, 9, '0') AS SIXTEEN_DIGIT_NUMBER,
    a.COMPANY,
    a.DIVISION,
    a.FRANCHISE_NUMBER,
    a.FIRST_NAME,
    a.LAST_NAME,
    a.BUSINESS_NAME,
    a.BILLING_STATUS,
    a.ACCOUNT_STATUS,
    a.SECURITY_CODE,
    a.BILL_TYPE,
    a.DELINQUENCY_STATUS,
    a.BIRTH_DATE,
    a.TAX_TYPE,
    a.TAX_IDENTIFIER,
    a.DRIVERS_LICENSE_NUM,
    a.PERSISTENT_ID,
    a.CONTROLLER_ID,
    a.VCM,
    a.INSTALL_DATE,
    a.DISCONNECTED_DATE,
    a.CUSTOMER_CATEGORY,
    a.CUSTOMER_TYPE,
    aa.ADDR_LINE1 AS SERVICE_ADDR_LINE1,
    aa.ADDR_LINE2 AS SERVICE_ADDR_LINE2,
    aa.CITY AS SERVICE_CITY,
    aa.STATE AS SERVICE_STATE,
    aa.ZIP5 AS SERVICE_ZIP5,
    aa.ZIP4 AS SERVICE_ZIP4,
    aa.NODE_NUMBER,
    aa.HOUSE_NUMBER,
    aa.HOUSE_DEVELOPMENT_NUMBER,
    bta.BILLTO_ADDR_LINE1 AS BILLTO_ADDR_LINE1,
    bta.BILLTO_ADDR_LINE2 AS BILLTO_ADDR_LINE2,
    bta.BILLTO_CITY AS BILLTO_CITY,
    bta.BILLTO_STATE AS BILLTO_STATE,
    bta.BILLTO_ZIP5 AS BILLTO_ZIP5,
    bta.BILLTO_ZIP4 AS BILLTO_ZIP4,
    bta.BILLTO_FIRST_NAME || ' ' || bta.BILLTO_LAST_NAME AS BILLTO_CUSTOMER_NAME,
    bta.BILLTO_BUSINESS_NAME AS BILLTO_BUSINESS_NAME,
    ac.ACCOUNT_CONTACT_ID,
    ac.NOTIFICATION_METHOD,
    ac.CONTACT_TYPE,
    ac.CONTACT_VALUE,
    ac.PRIMARY AS PRIMARY_CONTACT,
    ac.OPT_IN_FLAG,
    apc.ACCOUNT_PROD_CATEGORY_ID,
    apc.PROD_CATEGORY_CODE,
    apc.CUST_PROD_CAT_STATUS,
    apc.CUST_PROD_CAT_STATUS_DATE,
    at.TO_ACCOUNT_ID,
    at.FROM_ACCOUNT_ID,
    at.TRANSFER_STATUS,
    asr.SEASONAL_SUSPEND_START,
    asr.SEASONAL_SUSPEND_END,
    aau.AUTH_USER,
    ma.MASTER_ACCOUNT_ID,
    aet.TRANSACTION_ID,
    aet.EVENT_TIMESTAMP,
    aet.EVENT_ID,
    aet.CORRELATION_ID,
    aet.ORIGIN,
    aet.SYNC_STATUS,
    aet.ERR_MSG,
    a.CREATED_DT AS ACCOUNT_CREATED_DT,
    a.CREATED_BY AS ACCOUNT_CREATED_BY,
    a.UPDATED_DT AS ACCOUNT_UPDATED_DT,
    a.UPDATED_BY AS ACCOUNT_UPDATED_BY

FROM
    BILLING_EVENT.ACCOUNT a
    INNER JOIN BILLING_EVENT.HOUSE_ADDRESS aa
        ON a.HOUSE_ADDR_ID = aa.HOUSE_ADDR_ID
    LEFT JOIN BILLING_EVENT.BILLTO_ADDRESS bta
        ON a.ACCOUNT_ID = bta.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.ACCOUNT_CONTACT ac
        ON a.ACCOUNT_ID = ac.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.ACCOUNT_PROD_CATEGORY apc
        ON a.ACCOUNT_ID = apc.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.ACCOUNT_TRANSFER at
        ON a.ACCOUNT_ID = at.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.SEASONAL_ACCOUNT asr
        ON a.ACCOUNT_ID = asr.ACCOUNT_ID
    LEFT JOIN (
        SELECT ACCOUNT_ID, TRANSACTION_ID, EVENT_TIMESTAMP, EVENT_ID,
               CORRELATION_ID, ORIGIN, SYNC_STATUS, ERR_MSG
        FROM (
            SELECT aevt.ACCOUNT_ID, aevt.TRANSACTION_ID, aevt.EVENT_TIMESTAMP, aevt.EVENT_ID,
                   aevt.CORRELATION_ID, aevt.ORIGIN, aevt.SYNC_STATUS, aevt.ERR_MSG,
                   ROW_NUMBER() OVER (PARTITION BY aevt.ACCOUNT_ID
                                      ORDER BY aevt.EVENT_TIMESTAMP DESC) AS rn
            FROM BILLING_EVENT.ACCOUNT_EVENT_TRANSACTION aevt
            WHERE aevt."RESOURCE" = 'account'
        )
        WHERE rn = 1
    ) aet
        ON a.ACCOUNT_ID = aet.ACCOUNT_ID
   LEFT JOIN BILLING_EVENT.MASTER_ACCOUNT ma
        ON a.ACCOUNT_ID = ma.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.ACCOUNT_AUTH_USER aau
        ON a.ACCOUNT_ID = aau.ACCOUNT_ID
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
CREATE OR REPLACE FORCE EDITIONABLE VIEW "BILLING_EVENT"."ACCOUNT_EVENT_VW" ("ACCOUNT_ID", "SITE_ID", "ACCOUNT_NUMBER", "TWELVE_DIGIT_NUMBER", "THIRTEEN_DIGIT_NUMBER", "SIXTEEN_DIGIT_NUMBER", "COMPANY", "DIVISION", "FRANCHISE_NUMBER", "FIRST_NAME", "LAST_NAME", "BUSINESS_NAME", "BILLING_STATUS", "ACCOUNT_STATUS", "SECURITY_CODE", "BILL_TYPE", "DELINQUENCY_STATUS", "BIRTH_DATE", "TAX_TYPE", "TAX_IDENTIFIER", "DRIVERS_LICENSE_NUM", "PERSISTENT_ID", "CONTROLLER_ID", "VCM", "INSTALL_DATE", "DISCONNECTED_DATE", "CUSTOMER_CATEGORY", "CUSTOMER_TYPE", "SERVICE_ADDR_LINE1", "SERVICE_ADDR_LINE2", "SERVICE_CITY", "SERVICE_STATE", "SERVICE_ZIP5", "SERVICE_ZIP4", "NODE_NUMBER", "HOUSE_NUMBER", "HOUSE_DEVELOPMENT_NUMBER", "BILLTO_ADDR_LINE1", "BILLTO_ADDR_LINE2", "BILLTO_CITY", "BILLTO_STATE", "BILLTO_ZIP5", "BILLTO_ZIP4", "BILLTO_CUSTOMER_NAME", "BILLTO_BUSINESS_NAME", "ACCOUNT_CONTACT_ID", "NOTIFICATION_METHOD", "CONTACT_TYPE", "CONTACT_VALUE", "PRIMARY_CONTACT", "OPT_IN_FLAG", "ACCOUNT_PROD_CATEGORY_ID", "PROD_CATEGORY_CODE", "CUST_PROD_CAT_STATUS", "CUST_PROD_CAT_STATUS_DATE", "FROM_ACCOUNT_ID", "TRANSFER_STATUS", "SEASONAL_SUSPEND_START", "SEASONAL_SUSPEND_END", "AUTH_USER", "MASTER_ACCOUNT", "TRANSACTION_ID", "EVENT_TIMESTAMP", "EVENT_ID", "CORRELATION_ID", "ORIGIN", "SYNC_STATUS", "ERR_MSG", "ACCOUNT_CREATED_DT", "ACCOUNT_CREATED_BY", "ACCOUNT_UPDATED_DT", "ACCOUNT_UPDATED_BY") AS
  SELECT
    a.ACCOUNT_ID,
    a.SITE_ID,
    a.ACCOUNT_NUMBER,
    LPAD(a.SITE_ID, 3, '0') || LPAD(a.ACCOUNT_NUMBER, 9, '0') AS TWELVE_DIGIT_NUMBER,
    LPAD(a.COMPANY, 2, '0') || LPAD(a.DIVISION, 2, '0') || LPAD(a.ACCOUNT_NUMBER, 9, '0') AS THIRTEEN_DIGIT_NUMBER,
    LPAD(a.SITE_ID, 3, '0') || LPAD(a.COMPANY, 2, '0') || LPAD(a.DIVISION, 2, '0') || LPAD(a.ACCOUNT_NUMBER, 9, '0') AS SIXTEEN_DIGIT_NUMBER,
    a.COMPANY,
    a.DIVISION,
    a.FRANCHISE_NUMBER,
    a.FIRST_NAME,
    a.LAST_NAME,
    a.BUSINESS_NAME,
    a.BILLING_STATUS,
    a.ACCOUNT_STATUS,
    a.SECURITY_CODE,
    a.BILL_TYPE,
    a.DELINQUENCY_STATUS,
    a.BIRTH_DATE,
    a.TAX_TYPE,
    a.TAX_IDENTIFIER,
    a.DRIVERS_LICENSE_NUM,
    a.PERSISTENT_ID,
    a.CONTROLLER_ID,
    a.VCM,
    a.INSTALL_DATE,
    a.DISCONNECTED_DATE,
    a.CUSTOMER_CATEGORY,
    a.CUSTOMER_TYPE,
    aa.ADDR_LINE1 AS SERVICE_ADDR_LINE1,
    aa.ADDR_LINE2 AS SERVICE_ADDR_LINE2,
    aa.CITY AS SERVICE_CITY,
    aa.STATE AS SERVICE_STATE,
    aa.ZIP5 AS SERVICE_ZIP5,
    aa.ZIP4 AS SERVICE_ZIP4,
    aa.NODE_NUMBER,
    aa.HOUSE_NUMBER,
    aa.HOUSE_DEVELOPMENT_NUMBER,
    bta.BILLTO_ADDR_LINE1 AS BILLTO_ADDR_LINE1,
    bta.BILLTO_ADDR_LINE2 AS BILLTO_ADDR_LINE2,
    bta.BILLTO_CITY AS BILLTO_CITY,
    bta.BILLTO_STATE AS BILLTO_STATE,
    bta.BILLTO_ZIP5 AS BILLTO_ZIP5,
    bta.BILLTO_ZIP4 AS BILLTO_ZIP4,
    bta.BILLTO_FIRST_NAME || ' ' || bta.BILLTO_LAST_NAME AS BILLTO_CUSTOMER_NAME,
    bta.BILLTO_BUSINESS_NAME AS BILLTO_BUSINESS_NAME,
    ac.ACCOUNT_CONTACT_ID,
    ac.NOTIFICATION_METHOD,
    ac.CONTACT_TYPE,
    ac.CONTACT_VALUE,
    ac.PRIMARY AS PRIMARY_CONTACT,
    ac.OPT_IN_FLAG,
    apc.ACCOUNT_PROD_CATEGORY_ID,
    apc.PROD_CATEGORY_CODE,
    apc.CUST_PROD_CAT_STATUS,
    apc.CUST_PROD_CAT_STATUS_DATE,
    at.FROM_ACCOUNT_ID,
    at.TRANSFER_STATUS,
    asr.SEASONAL_SUSPEND_START,
    asr.SEASONAL_SUSPEND_END,
    aau.AUTH_USER,
    ma.MASTER_ACCOUNT_ID,
    aet.TRANSACTION_ID,
    aet.EVENT_TIMESTAMP,
    aet.EVENT_ID,
    aet.CORRELATION_ID,
    aet.ORIGIN,
    aet.SYNC_STATUS,
    aet.ERR_MSG,
    a.CREATED_DT AS ACCOUNT_CREATED_DT,
    a.CREATED_BY AS ACCOUNT_CREATED_BY,
    a.UPDATED_DT AS ACCOUNT_UPDATED_DT,
    a.UPDATED_BY AS ACCOUNT_UPDATED_BY

FROM
    BILLING_EVENT.ACCOUNT a
    INNER JOIN BILLING_EVENT.HOUSE_ADDRESS aa
        ON a.HOUSE_ADDR_ID = aa.HOUSE_ADDR_ID
    LEFT JOIN BILLING_EVENT.BILLTO_ADDRESS bta
        ON a.ACCOUNT_ID = bta.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.ACCOUNT_CONTACT ac
        ON a.ACCOUNT_ID = ac.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.ACCOUNT_PROD_CATEGORY apc
        ON a.ACCOUNT_ID = apc.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.ACCOUNT_TRANSFER at
        ON a.ACCOUNT_ID = at.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.SEASONAL_ACCOUNT asr
        ON a.ACCOUNT_ID = asr.ACCOUNT_ID
    LEFT JOIN (
        SELECT ACCOUNT_ID, TRANSACTION_ID, EVENT_TIMESTAMP, EVENT_ID,
               CORRELATION_ID, ORIGIN, SYNC_STATUS, ERR_MSG
        FROM (
            SELECT aevt.ACCOUNT_ID, aevt.TRANSACTION_ID, aevt.EVENT_TIMESTAMP, aevt.EVENT_ID,
                   aevt.CORRELATION_ID, aevt.ORIGIN, aevt.SYNC_STATUS, aevt.ERR_MSG,
                   ROW_NUMBER() OVER (PARTITION BY aevt.ACCOUNT_ID
                                      ORDER BY aevt.EVENT_TIMESTAMP DESC) AS rn
            FROM BILLING_EVENT.ACCOUNT_EVENT_TRANSACTION aevt
            WHERE aevt."RESOURCE" = 'account'
        )
        WHERE rn = 1
    ) aet
        ON a.ACCOUNT_ID = aet.ACCOUNT_ID
   LEFT JOIN BILLING_EVENT.MASTER_ACCOUNT ma
        ON a.ACCOUNT_ID = ma.ACCOUNT_ID
    LEFT JOIN BILLING_EVENT.ACCOUNT_AUTH_USER aau
        ON a.ACCOUNT_ID = aau.ACCOUNT_ID
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.59" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Comment on BILLING_EVENT.ACCOUNT_EVENT_VW [source 09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql:127]</comment>
        <setTableRemarks tableName="ACCOUNT_EVENT_VW" schemaName="BILLING_EVENT" remarks="Account event view with all related details. Returns multiple rows per account for contacts and product categories."/>
        <rollback>
            <sql>
                <![CDATA[
COMMENT ON TABLE BILLING_EVENT.ACCOUNT_EVENT_VW IS ''
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.60" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>GRANT BILLING_EVENT.ACCOUNT_EVENT_VW [source 09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql:128]</comment>
        <sql><![CDATA[
GRANT SELECT ON "BILLING_EVENT"."ACCOUNT_EVENT_VW" TO "BILLING_EVENT_READ_ROLE"
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
REVOKE SELECT ON BILLING_EVENT.ACCOUNT_EVENT_VW FROM BILLING_EVENT_READ_ROLE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.61" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Drop column(s) STATUS from BILLING_EVENT.SHADOW_ORDER [source 10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:18]</comment>
        <sql><![CDATA[
ALTER TABLE "BILLING_EVENT"."SHADOW_ORDER"
DROP COLUMN STATUS CASCADE CONSTRAINTS
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER ADD (STATUS VARCHAR2(20))
]]>
            </sql>
            <sql>
                <![CDATA[
MERGE INTO BILLING_EVENT.SHADOW_ORDER t USING BILLING_EVENT.SHADOW_ORDER_BKP66 b ON (t.SHADOW_ORDER_ID = b.SHADOW_ORDER_ID) WHEN MATCHED THEN UPDATE SET t.STATUS = b.STATUS
]]>
            </sql>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER ADD CONSTRAINT CHK_SHADOW_STATUS CHECK (STATUS IN ('ACTIVE', 'TERMINATED_COID', 'TERMINATED_TTL', 'TERMINATED_CANCEL'))
]]>
            </sql>
            <sql>
                <![CDATA[
CREATE INDEX BILLING_EVENT.IDX_SHADOW_ORDER_ACCT ON BILLING_EVENT.SHADOW_ORDER (ACCOUNT_ID ASC, STATUS ASC) TABLESPACE "BILLING_EVENT_DATA"
]]>
            </sql>
            <sql>
                <![CDATA[
CREATE INDEX BILLING_EVENT.IDX_SHADOW_ORDER_TTL ON BILLING_EVENT.SHADOW_ORDER (STATUS ASC, TTL_EXPIRES_AT ASC) TABLESPACE "BILLING_EVENT_DATA"
]]>
            </sql>
            <sql>
                <![CDATA[
COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.STATUS IS 'ACTIVE, TERMINATED_COID, TERMINATED_TTL, TERMINATED_CANCEL'
]]>
            </sql>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER MODIFY (STATUS NOT NULL)
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.62" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Drop column(s) FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE from BILLING_EVENT.SHADOW_PRODUCT_ORDER [source 10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:32]</comment>
        <sql><![CDATA[
ALTER TABLE "BILLING_EVENT"."SHADOW_PRODUCT_ORDER"
DROP (FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE) CASCADE CONSTRAINTS
]]></sql>
        <rollback>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD (FREE_QUANTITY NUMBER(5) DEFAULT 0, PRODUCT_TYPE VARCHAR2(1), CHECKED_IN_STATUS VARCHAR2(1) DEFAULT 'I', CATEGORY_STATUS VARCHAR2(1) DEFAULT '2', PRODUCT_SEQUENCE NUMBER(5), CATEGORY_SEQUENCE NUMBER(3))
]]>
            </sql>
            <sql>
                <![CDATA[
MERGE INTO BILLING_EVENT.SHADOW_PRODUCT_ORDER t USING BILLING_EVENT.SHADOW_PRODUCT_ORDER_BKP67 b ON (t.SHADOW_PRODUCT_ORDER_ID = b.SHADOW_PRODUCT_ORDER_ID) WHEN MATCHED THEN UPDATE SET t.FREE_QUANTITY = b.FREE_QUANTITY, t.PRODUCT_TYPE = b.PRODUCT_TYPE, t.CHECKED_IN_STATUS = b.CHECKED_IN_STATUS, t.CATEGORY_STATUS = b.CATEGORY_STATUS, t.PRODUCT_SEQUENCE = b.PRODUCT_SEQUENCE, t.CATEGORY_SEQUENCE = b.CATEGORY_SEQUENCE
]]>
            </sql>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD CONSTRAINT UK_SHADOW_SVC_SEQ UNIQUE (SHADOW_ORDER_ID, PRODUCT_SEQUENCE)
]]>
            </sql>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD CONSTRAINT CHK_SHADOW_SVC_TYPE CHECK (PRODUCT_TYPE IN ('R', 'T'))
]]>
            </sql>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD CONSTRAINT CHK_SHADOW_CHECKED_IN CHECK (CHECKED_IN_STATUS IN ('I', 'A', 'D'))
]]>
            </sql>
            <sql>
                <![CDATA[
COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.PRODUCT_TYPE IS 'R=Recurring, T=Temporary (from catalog)'
]]>
            </sql>
            <sql>
                <![CDATA[
COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.CHECKED_IN_STATUS IS 'I=Install Pending (always for shadow), A=Active, D=Disconnect Pending'
]]>
            </sql>
            <sql>
                <![CDATA[
COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.CATEGORY_STATUS IS '2 = Pending Connect (always for shadow orders)'
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.63" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Drop column(s) STATUS from BILLING_EVENT.SHADOW_ORDER_AUDIT [source 11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:18]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <columnExists tableName="SHADOW_ORDER_AUDIT" columnName="STATUS" schemaName="BILLING_EVENT"/>
        </preConditions>
        <dropColumn tableName="SHADOW_ORDER_AUDIT" schemaName="BILLING_EVENT">
            <column name="STATUS"/>
        </dropColumn>
        <rollback>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_ORDER_AUDIT ADD (STATUS VARCHAR2(20))
]]>
            </sql>
            <sql>
                <![CDATA[
MERGE INTO BILLING_EVENT.SHADOW_ORDER_AUDIT t USING BILLING_EVENT.SHADOW_ORDER_AUDIT_BKP68 b ON (t.AUDIT_ID = b.AUDIT_ID) WHEN MATCHED THEN UPDATE SET t.STATUS = b.STATUS
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.64" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Drop column(s) FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE from BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT [source 11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:29]</comment>
        <preConditions onFail="MARK_RAN" onError="HALT">
            <columnExists tableName="SHADOW_PRODUCT_ORDER_AUDIT" columnName="FREE_QUANTITY" schemaName="BILLING_EVENT"/>
        </preConditions>
        <dropColumn tableName="SHADOW_PRODUCT_ORDER_AUDIT" schemaName="BILLING_EVENT">
            <column name="FREE_QUANTITY"/>
            <column name="PRODUCT_TYPE"/>
            <column name="CHECKED_IN_STATUS"/>
            <column name="CATEGORY_STATUS"/>
            <column name="PRODUCT_SEQUENCE"/>
            <column name="CATEGORY_SEQUENCE"/>
        </dropColumn>
        <rollback>
            <sql>
                <![CDATA[
ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT ADD (FREE_QUANTITY NUMBER(5), PRODUCT_TYPE VARCHAR2(1), CHECKED_IN_STATUS VARCHAR2(1), CATEGORY_STATUS VARCHAR2(1), PRODUCT_SEQUENCE NUMBER(5), CATEGORY_SEQUENCE NUMBER(3))
]]>
            </sql>
            <sql>
                <![CDATA[
MERGE INTO BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT t USING BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT_BKP69 b ON (t.AUDIT_ID = b.AUDIT_ID) WHEN MATCHED THEN UPDATE SET t.FREE_QUANTITY = b.FREE_QUANTITY, t.PRODUCT_TYPE = b.PRODUCT_TYPE, t.CHECKED_IN_STATUS = b.CHECKED_IN_STATUS, t.CATEGORY_STATUS = b.CATEGORY_STATUS, t.PRODUCT_SEQUENCE = b.PRODUCT_SEQUENCE, t.CATEGORY_SEQUENCE = b.CATEGORY_SEQUENCE
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.65" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create or replace trigger BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT [source 12_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql:15]</comment>
        <sql splitStatements="false" stripComments="false"><![CDATA[
CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
AFTER INSERT OR UPDATE OR DELETE ON BILLING_EVENT.SHADOW_ORDER
FOR EACH ROW
DECLARE
    v_action VARCHAR2(10);
    v_transaction_id VARCHAR2(100);
BEGIN
    IF INSERTING THEN
        v_action := 'INSERT';
    ELSIF UPDATING THEN
        v_action := 'UPDATE';
    ELSIF DELETING THEN
        v_action := 'DELETE';
    END IF;

    v_transaction_id := SYS_GUID();

    INSERT INTO BILLING_EVENT.SHADOW_ORDER_AUDIT (
        AUDIT_ID,
        AUDIT_TIMESTAMP,
        AUDIT_ACTION,
        AUDIT_TRANSACTION_ID,
        SHADOW_ORDER_ID,
        CUSTOMER_ORDER_ID,
        ACCOUNT_ID,
        ACCOUNT_NUMBER,
        SITE_ID,
        ORDER_TYPE,
        TTL_EXPIRES_AT,
        CREATED_DT,
        CREATED_BY,
        UPDATED_DT,
        UPDATED_BY
    ) VALUES (
        BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID.NEXTVAL,
        SYSTIMESTAMP,
        v_action,
        v_transaction_id,
        COALESCE(:NEW.SHADOW_ORDER_ID, :OLD.SHADOW_ORDER_ID),
        COALESCE(:NEW.CUSTOMER_ORDER_ID, :OLD.CUSTOMER_ORDER_ID),
        COALESCE(:NEW.ACCOUNT_ID, :OLD.ACCOUNT_ID),
        COALESCE(:NEW.ACCOUNT_NUMBER, :OLD.ACCOUNT_NUMBER),
        COALESCE(:NEW.SITE_ID, :OLD.SITE_ID),
        COALESCE(:NEW.ORDER_TYPE, :OLD.ORDER_TYPE),
        COALESCE(:NEW.TTL_EXPIRES_AT, :OLD.TTL_EXPIRES_AT),
        COALESCE(:NEW.CREATED_DT, :OLD.CREATED_DT),
        COALESCE(:NEW.CREATED_BY, :OLD.CREATED_BY),
        COALESCE(:NEW.UPDATED_DT, :OLD.UPDATED_DT),
        COALESCE(:NEW.UPDATED_BY, :OLD.UPDATED_BY)
    );
END;
]]></sql>
        <rollback>
            <sql splitStatements="false" stripComments="false" endDelimiter="\n/">
                <![CDATA[
CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
AFTER INSERT OR UPDATE OR DELETE ON BILLING_EVENT.SHADOW_ORDER
FOR EACH ROW
DECLARE
    v_action VARCHAR2(10);
    v_transaction_id VARCHAR2(100);
BEGIN
    IF INSERTING THEN
        v_action := 'INSERT';
    ELSIF UPDATING THEN
        v_action := 'UPDATE';
    ELSIF DELETING THEN
        v_action := 'DELETE';
    END IF;

    v_transaction_id := SYS_GUID();

    INSERT INTO BILLING_EVENT.SHADOW_ORDER_AUDIT (
        AUDIT_ID,
        AUDIT_TIMESTAMP,
        AUDIT_ACTION,
        AUDIT_TRANSACTION_ID,
        SHADOW_ORDER_ID,
        CUSTOMER_ORDER_ID,
        ACCOUNT_ID,
        ACCOUNT_NUMBER,
        SITE_ID,
        ORDER_TYPE,
        STATUS,
        TTL_EXPIRES_AT,
        CREATED_DT,
        CREATED_BY,
        UPDATED_DT,
        UPDATED_BY
    ) VALUES (
        BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID.NEXTVAL,
        SYSTIMESTAMP,
        v_action,
        v_transaction_id,
        COALESCE(:NEW.SHADOW_ORDER_ID, :OLD.SHADOW_ORDER_ID),
        COALESCE(:NEW.CUSTOMER_ORDER_ID, :OLD.CUSTOMER_ORDER_ID),
        COALESCE(:NEW.ACCOUNT_ID, :OLD.ACCOUNT_ID),
        COALESCE(:NEW.ACCOUNT_NUMBER, :OLD.ACCOUNT_NUMBER),
        COALESCE(:NEW.SITE_ID, :OLD.SITE_ID),
        COALESCE(:NEW.ORDER_TYPE, :OLD.ORDER_TYPE),
        COALESCE(:NEW.STATUS, :OLD.STATUS),
        COALESCE(:NEW.TTL_EXPIRES_AT, :OLD.TTL_EXPIRES_AT),
        COALESCE(:NEW.CREATED_DT, :OLD.CREATED_DT),
        COALESCE(:NEW.CREATED_BY, :OLD.CREATED_BY),
        COALESCE(:NEW.UPDATED_DT, :OLD.UPDATED_DT),
        COALESCE(:NEW.UPDATED_BY, :OLD.UPDATED_BY)
    );
END;
]]>
            </sql>
        </rollback>
    </changeSet>

    <changeSet id="SOL_SERVICES.1.34.1.0.66" author="SOL_DATA" labels="SOL_SERVICES_1.34">
        <comment>Create or replace trigger BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT [source 13_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_ALTER_DDL.sql:17]</comment>
        <sql splitStatements="false" stripComments="false"><![CDATA[
CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT
AFTER INSERT OR UPDATE OR DELETE ON BILLING_EVENT.SHADOW_PRODUCT_ORDER
FOR EACH ROW
DECLARE
    v_action VARCHAR2(10);
    v_transaction_id VARCHAR2(100);
BEGIN
    IF INSERTING THEN
        v_action := 'INSERT';
    ELSIF UPDATING THEN
        v_action := 'UPDATE';
    ELSIF DELETING THEN
        v_action := 'DELETE';
    END IF;

    v_transaction_id := SYS_GUID();

    INSERT INTO BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT (
        AUDIT_ID,
        AUDIT_TIMESTAMP,
        AUDIT_ACTION,
        AUDIT_TRANSACTION_ID,
        SHADOW_PRODUCT_ORDER_ID,
        SHADOW_ORDER_ID,
        PRODUCT_ID,
        PAID_QUANTITY,
        OCCURRENCE_NUMBER,
        CATEGORY_CODE,
        CREATED_DT,
        CREATED_BY,
        UPDATED_DT,
        UPDATED_BY
    ) VALUES (
        BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID.NEXTVAL,
        SYSTIMESTAMP,
        v_action,
        v_transaction_id,
        COALESCE(:NEW.SHADOW_PRODUCT_ORDER_ID, :OLD.SHADOW_PRODUCT_ORDER_ID),
        COALESCE(:NEW.SHADOW_ORDER_ID, :OLD.SHADOW_ORDER_ID),
        COALESCE(:NEW.PRODUCT_ID, :OLD.PRODUCT_ID),
        COALESCE(:NEW.PAID_QUANTITY, :OLD.PAID_QUANTITY),
        COALESCE(:NEW.OCCURRENCE_NUMBER, :OLD.OCCURRENCE_NUMBER),
        COALESCE(:NEW.CATEGORY_CODE, :OLD.CATEGORY_CODE),
        COALESCE(:NEW.CREATED_DT, :OLD.CREATED_DT),
        COALESCE(:NEW.CREATED_BY, :OLD.CREATED_BY),
        COALESCE(:NEW.UPDATED_DT, :OLD.UPDATED_DT),
        COALESCE(:NEW.UPDATED_BY, :OLD.UPDATED_BY)
    );
END;
]]></sql>
        <rollback>
            <sql splitStatements="false" stripComments="false" endDelimiter="\n/">
                <![CDATA[
CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT
AFTER INSERT OR UPDATE OR DELETE ON BILLING_EVENT.SHADOW_PRODUCT_ORDER
FOR EACH ROW
DECLARE
    v_action VARCHAR2(10);
    v_transaction_id VARCHAR2(100);
BEGIN
    IF INSERTING THEN
        v_action := 'INSERT';
    ELSIF UPDATING THEN
        v_action := 'UPDATE';
    ELSIF DELETING THEN
        v_action := 'DELETE';
    END IF;

    v_transaction_id := SYS_GUID();

    INSERT INTO BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT (
        AUDIT_ID,
        AUDIT_TIMESTAMP,
        AUDIT_ACTION,
        AUDIT_TRANSACTION_ID,
        SHADOW_PRODUCT_ORDER_ID,
        SHADOW_ORDER_ID,
        PRODUCT_ID,
        PAID_QUANTITY,
        FREE_QUANTITY,
        CHECKED_IN_STATUS,
        OCCURRENCE_NUMBER,
        PRODUCT_TYPE,
        PRODUCT_SEQUENCE,
        CATEGORY_CODE,
        CATEGORY_STATUS,
        CATEGORY_SEQUENCE,
        CREATED_DT,
        CREATED_BY,
        UPDATED_DT,
        UPDATED_BY
    ) VALUES (
        BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID.NEXTVAL,
        SYSTIMESTAMP,
        v_action,
        v_transaction_id,
        COALESCE(:NEW.SHADOW_PRODUCT_ORDER_ID, :OLD.SHADOW_PRODUCT_ORDER_ID),
        COALESCE(:NEW.SHADOW_ORDER_ID, :OLD.SHADOW_ORDER_ID),
        COALESCE(:NEW.PRODUCT_ID, :OLD.PRODUCT_ID),
        COALESCE(:NEW.PAID_QUANTITY, :OLD.PAID_QUANTITY),
        COALESCE(:NEW.FREE_QUANTITY, :OLD.FREE_QUANTITY),
        COALESCE(:NEW.CHECKED_IN_STATUS, :OLD.CHECKED_IN_STATUS),
        COALESCE(:NEW.OCCURRENCE_NUMBER, :OLD.OCCURRENCE_NUMBER),
        COALESCE(:NEW.PRODUCT_TYPE, :OLD.PRODUCT_TYPE),
        COALESCE(:NEW.PRODUCT_SEQUENCE, :OLD.PRODUCT_SEQUENCE),
        COALESCE(:NEW.CATEGORY_CODE, :OLD.CATEGORY_CODE),
        COALESCE(:NEW.CATEGORY_STATUS, :OLD.CATEGORY_STATUS),
        COALESCE(:NEW.CATEGORY_SEQUENCE, :OLD.CATEGORY_SEQUENCE),
        COALESCE(:NEW.CREATED_DT, :OLD.CREATED_DT),
        COALESCE(:NEW.CREATED_BY, :OLD.CREATED_BY),
        COALESCE(:NEW.UPDATED_DT, :OLD.UPDATED_DT),
        COALESCE(:NEW.UPDATED_BY, :OLD.UPDATED_BY)
    );
END;
]]>
            </sql>
        </rollback>
    </changeSet>
</databaseChangeLog>
```

Formatted SQL package: 19 file(s). First file `vibehub_1.34_deploy/01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql`:

```sql
--liquibase formatted sql

--changeset SOL_DATA:SOL_SERVICES.1.34.1.0.1-pre

Insert Into LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER (CHANGESET_ID,SCHEMA_NAME,SCRIPT_NAME,RELEASE_NUMBER,OBJECT_TYPE,OBJECT_NAME,SQL_LOCATION,ACTION,STATUS,COUNT_BEFORE_CHANGE,COUNT_AFTER_CHANGE,ROLLBACK_FLAG) VALUES ('SOL_SERVICES.1.34.1.0.1','BILLING_EVENT','01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql','SOL_SERVICES 1.34','Table/Index','SHADOW_ORDER','/opt/scripts/','Create Table','PENDING',(select count (*) from DBA_TABLES where OWNER = 'BILLING_EVENT'),0,0);

COMMIT;
--rollback DELETE FROM LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER WHERE CHANGESET_ID = 'SOL_SERVICES.1.34.1.0.1';

--changeset SOL_DATA:SOL_SERVICES.1.34.1.0.1
--comment: Create Sequence, Create Table, Create Index, Comment, Grant - SEQ_SHADOW_ORDER_ID, SHADOW_ORDER, IDX_SHADOW_ORDER_ACCT, IDX_SHADOW_ORDER_TTL

-- =====================================================
-- SEQUENCES FOR PRIMARY KEYS
-- =====================================================
CREATE SEQUENCE BILLING_EVENT.SEQ_SHADOW_ORDER_ID
  START WITH 1
  INCREMENT BY 1
  NOCACHE
  NOCYCLE;

-- =====================================================
-- Table: SHADOW_ORDER
-- Purpose: Core shadow order tracking with lifecycle mgmt
-- =====================================================
CREATE TABLE BILLING_EVENT.SHADOW_ORDER (
   SHADOW_ORDER_ID      NUMBER                NOT NULL,
   CUSTOMER_ORDER_ID    VARCHAR2(50)          NOT NULL,
   ACCOUNT_ID           NUMBER                NOT NULL,
   ACCOUNT_NUMBER       NUMBER(9)             NOT NULL,
   SITE_ID              NUMBER(3)             NOT NULL,
   ORDER_TYPE           VARCHAR2(20)          NOT NULL,
   STATUS               VARCHAR2(20)          NOT NULL,
   TTL_EXPIRES_AT       TIMESTAMP WITH TIME ZONE NOT NULL,
   CREATED_DT           TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
   CREATED_BY           VARCHAR2(30),
   UPDATED_DT           TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
   UPDATED_BY           VARCHAR2(30),
   CONSTRAINT PK_SHADOW_ORDER PRIMARY KEY (SHADOW_ORDER_ID),
   CONSTRAINT UK_SHADOW_ORDER_COID UNIQUE (CUSTOMER_ORDER_ID),
   CONSTRAINT FK_SHADOW_ORDER_ACCOUNT FOREIGN KEY (ACCOUNT_ID)
      REFERENCES BILLING_EVENT.ACCOUNT (ACCOUNT_ID),
   CONSTRAINT CHK_SHADOW_ORDER_TYPE CHECK (ORDER_TYPE IN ('Install', 'Change', 'Disconnect')),
   CONSTRAINT CHK_SHADOW_STATUS CHECK (STATUS IN ('ACTIVE', 'TERMINATED_COID', 'TERMINATED_TTL', 'TERMINATED_CANCEL'))
)
TABLESPACE "BILLING_EVENT_DATA"
NOLOGGING;

-- =====================================================
-- Note: CUSTOMER_ORDER_ID is already indexed by the unique constraint UK_SHADOW_ORDER_COID,
-- so a separate IDX_SHADOW_ORDER_COID index is not required.
-- =====================================================
CREATE INDEX BILLING_EVENT.IDX_SHADOW_ORDER_ACCT ON BILLING_EVENT.SHADOW_ORDER (ACCOUNT_ID ASC, STATUS ASC) TABLESPACE "BILLING_EVENT_DATA";

CREATE INDEX BILLING_EVENT.IDX_SHADOW_ORDER_TTL ON BILLING_EVENT.SHADOW_ORDER (STATUS ASC, TTL_EXPIRES_AT ASC) TABLESPACE "BILLING_EVENT_DATA";

COMMENT ON TABLE BILLING_EVENT.SHADOW_ORDER IS
'Shadow Selfie core order table. Holds in-flight manual orders from CBForce. References existing ACCOUNT table - no data duplication. Blocks ICOMS notification events until order completion or TTL expiry.';

COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.SHADOW_ORDER_ID IS 'Primary key - MW generated';

COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.CUSTOMER_ORDER_ID IS 'COID from CBForce - termination correlation key';

COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.ACCOUNT_ID IS 'Foreign key to BILLING_EVENT.ACCOUNT - references existing Selfie account';

COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.ACCOUNT_NUMBER IS 'ICOMS account number (denormalized from ACCOUNT for lookup)';

COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.SITE_ID IS 'ICOMS site id (denormalized from ACCOUNT for lookup)';

COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.ORDER_TYPE IS 'Install, Change, or Disconnect';

COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.STATUS IS 'ACTIVE, TERMINATED_COID, TERMINATED_TTL, TERMINATED_CANCEL';

COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.TTL_EXPIRES_AT IS 'Shadow expiration timestamp (CREATED_DT + TTL duration)';

-- =====================================================
-- GRANTS ON MAIN TABLES
-- SHADOW_ORDER Table
-- =====================================================
GRANT SELECT ON "BILLING_EVENT"."SHADOW_ORDER" TO "BILLING_EVENT_READ_ROLE";

GRANT SELECT, INSERT, UPDATE, DELETE ON "BILLING_EVENT"."SHADOW_ORDER" TO "BILLING_EVENT_WRITE_ROLE";

-- =====================================================
-- GRANTS ON SEQUENCES - PRIMARY KEY SEQUENCES
-- =====================================================
GRANT SELECT ON "BILLING_EVENT"."SEQ_SHADOW_ORDER_ID" TO "BILLING_EVENT_READ_ROLE";

--rollback DROP TABLE BILLING_EVENT.SHADOW_ORDER CASCADE CONSTRAINTS;
--rollback DROP SEQUENCE BILLING_EVENT.SEQ_SHADOW_ORDER_ID;

--changeset SOL_DATA:SOL_SERVICES.1.34.1.0.1-post

UPDATE LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER SET COUNT_AFTER_CHANGE = (select count (*) from DBA_TABLES where OWNER = 'BILLING_EVENT'), STATUS = 'COMPLETED' WHERE CHANGESET_ID = 'SOL_SERVICES.1.34.1.0.1';
COMMIT;
--rollback UPDATE LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER SET STATUS = 'ROLLED_BACK', ROLLBACK_FLAG = 1 WHERE CHANGESET_ID = 'SOL_SERVICES.1.34.1.0.1';
```

## 3. Rollback Section

| # | Object | Rollback | Complete | Notes |
|---|---|---|---|---|
| 1 | BILLING_EVENT.SEQ_SHADOW_ORDER_ID | `DROP SEQUENCE BILLING_EVENT.SEQ_SHADOW_ORDER_ID` | yes |  |
| 2 | BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID | `DROP SEQUENCE BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID` | yes |  |
| 3 | BILLING_EVENT.SHADOW_ORDER | `DROP TABLE BILLING_EVENT.SHADOW_ORDER CASCADE CONSTRAINTS` | yes |  |
| 4 | BILLING_EVENT.IDX_SHADOW_ORDER_ACCT | `DROP INDEX BILLING_EVENT.IDX_SHADOW_ORDER_ACCT` | yes |  |
| 5 | BILLING_EVENT.IDX_SHADOW_ORDER_TTL | `DROP INDEX BILLING_EVENT.IDX_SHADOW_ORDER_TTL` | yes |  |
| 6 | BILLING_EVENT.SHADOW_ORDER | `COMMENT ON TABLE BILLING_EVENT.SHADOW_ORDER IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 7 | BILLING_EVENT.SHADOW_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.SHADOW_ORDER_ID IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 8 | BILLING_EVENT.SHADOW_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.CUSTOMER_ORDER_ID IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 9 | BILLING_EVENT.SHADOW_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.ACCOUNT_ID IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 10 | BILLING_EVENT.SHADOW_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.ACCOUNT_NUMBER IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 11 | BILLING_EVENT.SHADOW_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.SITE_ID IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 12 | BILLING_EVENT.SHADOW_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.ORDER_TYPE IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 13 | BILLING_EVENT.SHADOW_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.STATUS IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 14 | BILLING_EVENT.SHADOW_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.TTL_EXPIRES_AT IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 15 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `DROP TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER CASCADE CONSTRAINTS` | yes |  |
| 16 | BILLING_EVENT.IDX_SHADOW_SVC_PRODUCT | `DROP INDEX BILLING_EVENT.IDX_SHADOW_SVC_PRODUCT` | yes |  |
| 17 | BILLING_EVENT.IDX_SHADOW_SVC_CATEGORY | `DROP INDEX BILLING_EVENT.IDX_SHADOW_SVC_CATEGORY` | yes |  |
| 18 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `COMMENT ON TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 19 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.SHADOW_ORDER_ID IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 20 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.PRODUCT_ID IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 21 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.CATEGORY_CODE IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 22 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.CHECKED_IN_STATUS IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 23 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.OCCURRENCE_NUMBER IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 24 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.PRODUCT_TYPE IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 25 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.CATEGORY_STATUS IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 26 | BILLING_EVENT.SHADOW_ORDER | `REVOKE SELECT ON BILLING_EVENT.SHADOW_ORDER FROM BILLING_EVENT_READ_ROLE` | yes |  |
| 27 | BILLING_EVENT.SHADOW_ORDER | `REVOKE SELECT, INSERT, UPDATE, DELETE ON BILLING_EVENT.SHADOW_ORDER FROM BILLING_EVENT_WRITE_ROLE` | yes |  |
| 28 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `REVOKE SELECT ON BILLING_EVENT.SHADOW_PRODUCT_ORDER FROM BILLING_EVENT_READ_ROLE` | yes |  |
| 29 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `REVOKE SELECT, INSERT, UPDATE, DELETE ON BILLING_EVENT.SHADOW_PRODUCT_ORDER FROM BILLING_EVENT_WRITE_ROLE` | yes |  |
| 30 | BILLING_EVENT.SEQ_SHADOW_ORDER_ID | `REVOKE SELECT ON BILLING_EVENT.SEQ_SHADOW_ORDER_ID FROM BILLING_EVENT_READ_ROLE` | yes |  |
| 31 | BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID | `REVOKE SELECT ON BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID FROM BILLING_EVENT_READ_ROLE` | yes |  |
| 32 | BILLING_EVENT.TRG_SHADOW_ORDER_BEFORE | `DROP TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_BEFORE` | yes |  |
| 33 | BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_BEFORE | `DROP TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_BEFORE` | yes |  |
| 34 | BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID | `DROP SEQUENCE BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID` | yes |  |
| 35 | BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID | `DROP SEQUENCE BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID` | yes |  |
| 36 | BILLING_EVENT.SHADOW_ORDER_AUDIT | `DROP TABLE BILLING_EVENT.SHADOW_ORDER_AUDIT CASCADE CONSTRAINTS` | yes |  |
| 37 | BILLING_EVENT.IDX_SHADOW_ORDER_AUD_TS | `DROP INDEX BILLING_EVENT.IDX_SHADOW_ORDER_AUD_TS` | yes |  |
| 38 | BILLING_EVENT.IDX_SHADOW_ORDER_AUD_ID | `DROP INDEX BILLING_EVENT.IDX_SHADOW_ORDER_AUD_ID` | yes |  |
| 39 | BILLING_EVENT.IDX_SHADOW_ORDER_AUD_COID | `DROP INDEX BILLING_EVENT.IDX_SHADOW_ORDER_AUD_COID` | yes |  |
| 40 | BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT | `DROP TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT CASCADE CONSTRAINTS` | yes |  |
| 41 | BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_TS | `DROP INDEX BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_TS` | yes |  |
| 42 | BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_ID | `DROP INDEX BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_ID` | yes |  |
| 43 | BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_SOID | `DROP INDEX BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_SOID` | yes |  |
| 44 | BILLING_EVENT.SHADOW_ORDER_AUDIT | `REVOKE SELECT ON BILLING_EVENT.SHADOW_ORDER_AUDIT FROM BILLING_EVENT_READ_ROLE` | yes |  |
| 45 | BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT | `REVOKE SELECT ON BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT FROM BILLING_EVENT_READ_ROLE` | yes |  |
| 46 | BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID | `REVOKE SELECT ON BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID FROM BILLING_EVENT_READ_ROLE` | yes |  |
| 47 | BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID | `REVOKE SELECT ON BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID FROM BILLING_EVENT_READ_ROLE` | yes |  |
| 48 | BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT | `DROP TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT` | yes |  |
| 49 | BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT | `DROP TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT` | yes |  |
| 50 | BILLING_EVENT.FK_ACCT_TRANSFER_FROM_ACCT | `ALTER TABLE BILLING_EVENT.ACCOUNT_TRANSFER ADD CONSTRAINT FK_ACCT_TRANSFER_FROM_ACCT FOREIGN KEY (FROM_ACCOUNT_ID) REFERENCES BILLING_EVENT.ACCOUNT (ACCOUNT_ID)` | yes | Re-adding FK FK_ACCT_TRANSFER_FROM_ACCT fails if orphan rows were created meanwhile - delete/repair them first. |
| 51 | BILLING_EVENT.ACCOUNT_TRANSFER | `ALTER TABLE BILLING_EVENT.ACCOUNT_TRANSFER MODIFY (FROM_ACCOUNT_ID NOT NULL)` | yes | Re-applying NOT NULL on FROM_ACCOUNT_ID fails if NULL rows were written after deploy: UPDATE/DELETE them first. |
| 52 | BILLING_EVENT.ACCOUNT_TRANSFER | `ALTER TABLE BILLING_EVENT.ACCOUNT_TRANSFER DROP COLUMN TO_ACCOUNT_ID` | yes |  |
| 53 | BILLING_EVENT.ACCOUNT_TRANSFER | `MERGE INTO BILLING_EVENT.ACCOUNT_TRANSFER t USING BILLING_EVENT.ACCOUNT_TRANSFER_BKP53 b ON (t.ACCOUNT_TRANSFER_ID = b.ACCOUNT_TRANSFER_ID) WHEN MATCHED THEN UPDATE SET t.TO_ACCOUNT_ID = b.TO_ACCOUNT_ID`<br>**backup first:** CREATE TABLE BILLING_EVENT.ACCOUNT_TRANSFER_BKP53 AS SELECT * FROM BILLING_EVENT.ACCOUNT_TRANSFER | yes | Pre-update values restored from ACCOUNT_TRANSFER_BKP53 by primary key. |
| 54 | BILLING_EVENT.IDX_ACCOUNT_HOUSE_ADDR_ID | `DROP INDEX BILLING_EVENT.IDX_ACCOUNT_HOUSE_ADDR_ID` | yes |  |
| 55 | BILLING_EVENT.IDX_ACCT_DISC_DISCOUNT_ID | `DROP INDEX BILLING_EVENT.IDX_ACCT_DISC_DISCOUNT_ID` | yes |  |
| 56 | BILLING_EVENT.IDX_ACCT_DISC_PRODUCT_ID | `DROP INDEX BILLING_EVENT.IDX_ACCT_DISC_PRODUCT_ID` | yes |  |
| 57 | BILLING_EVENT.IDX_ACCT_PROD_PRODUCT_ID | `DROP INDEX BILLING_EVENT.IDX_ACCT_PROD_PRODUCT_ID` | yes |  |
| 58 | BILLING_EVENT.IDX_ACCT_PROD_PHONE_ACCT_ID | `DROP INDEX BILLING_EVENT.IDX_ACCT_PROD_PHONE_ACCT_ID` | yes |  |
| 59 | BILLING_EVENT.IDX_ACCT_PROD_PHONE_PROD_ID | `DROP INDEX BILLING_EVENT.IDX_ACCT_PROD_PHONE_PROD_ID` | yes |  |
| 60 | BILLING_EVENT.IDX_BILLTO_ADDR_ACCOUNT_ID | `DROP INDEX BILLING_EVENT.IDX_BILLTO_ADDR_ACCOUNT_ID` | yes |  |
| 61 | BILLING_EVENT.IDX_MASTER_ACCT_MASTER_ID | `DROP INDEX BILLING_EVENT.IDX_MASTER_ACCT_MASTER_ID` | yes |  |
| 62 | BILLING_EVENT.IDX_SEASONAL_ACCT_ACCOUNT_ID | `DROP INDEX BILLING_EVENT.IDX_SEASONAL_ACCT_ACCOUNT_ID` | yes |  |
| 63 | BILLING_EVENT.ACCOUNT_EVENT_VW | `CREATE OR REPLACE FORCE EDITIONABLE VIEW "BILLING_EVENT"."ACCOUNT_EVENT_VW" ("ACCOUNT_ID", "SITE_ID", "ACCOUNT_NUMBER", "TWELVE_DIGIT_NUMBER", "THIRTEEN_DIGIT_NUMBER", "SIXTEEN_DIGIT_NUMBER", "COMPANY", "DIVISION", "FRANCHISE_NUMBER", "FIRST_NAME", "LAST_NAME", "BUSINESS_NAME", "BILLING_STATUS", "ACCOUNT_STATUS", "SECURITY_CODE", "BILL_TYPE", "DELINQUENCY_STATUS", "BIRTH_DATE", "TAX_TYPE", "TAX_IDENTIFIER", "DRIVERS_LICENSE_NUM", "PERSISTENT_ID", "CONTROLLER_ID", "VCM", "INSTALL_DATE", "DISCONNECTED_DATE", "CUSTOMER_CATEGORY", "CUSTOMER_TYPE", "SERVICE_ADDR_LINE1", "SERVICE_ADDR_LINE2", "SERVICE_CITY", "SERVICE_STATE", "SERVICE_ZIP5", "SERVICE_ZIP4", "NODE_NUMBER", "HOUSE_NUMBER", "HOUSE_DEVELOPMENT_NUMBER", "BILLTO_ADDR_LINE1", "BILLTO_ADDR_LINE2", "BILLTO_CITY", "BILLTO_STATE", "BILLTO_ZIP5", "BILLTO_ZIP4", "BILLTO_CUSTOMER_NAME", "BILLTO_BUSINESS_NAME", "ACCOUNT_CONTACT_ID", "NOTIFICATION_METHOD", "CONTACT_TYPE", "CONTACT_VALUE", "PRIMARY_CONTACT", "OPT_IN_FLAG", "ACCOUNT_PROD_CATEGORY_ID", "PROD_CATEGORY_CODE", "CUST_PROD_CAT_STATUS", "CUST_PROD_CAT_STATUS_DATE", "FROM_ACCOUNT_ID", "TRANSFER_STATUS", "SEASONAL_SUSPEND_START", "SEASONAL_SUSPEND_END", "AUTH_USER", "MASTER_ACCOUNT", "TRANSACTION_ID", "EVENT_TIMESTAMP", "EVENT_ID", "CORRELATION_ID", "ORIGIN", "SYNC_STATUS", "ERR_MSG", "ACCOUNT_CREATED_DT", "ACCOUNT_CREATED_BY", "ACCOUNT_UPDATED_DT", "ACCOUNT_UPDATED_BY") AS ...<br>COMMENT ON TABLE BILLING_EVENT.ACCOUNT_EVENT_VW IS 'Account event view with all related details. Returns multiple rows per account for contacts and product categories.'` | yes | Restores the previous definition of BILLING_EVENT.ACCOUNT_EVENT_VW captured from baseline/earlier step. |
| 64 | BILLING_EVENT.ACCOUNT_EVENT_VW | `COMMENT ON TABLE BILLING_EVENT.ACCOUNT_EVENT_VW IS ''` | yes | No previous comment known - rollback blanks the comment. |
| 65 | BILLING_EVENT.ACCOUNT_EVENT_VW | `REVOKE SELECT ON BILLING_EVENT.ACCOUNT_EVENT_VW FROM BILLING_EVENT_READ_ROLE` | yes |  |
| 66 | BILLING_EVENT.SHADOW_ORDER | `ALTER TABLE BILLING_EVENT.SHADOW_ORDER ADD (STATUS VARCHAR2(20))<br>MERGE INTO BILLING_EVENT.SHADOW_ORDER t USING BILLING_EVENT.SHADOW_ORDER_BKP66 b ON (t.SHADOW_ORDER_ID = b.SHADOW_ORDER_ID) WHEN MATCHED THEN UPDATE SET t.STATUS = b.STATUS<br>ALTER TABLE BILLING_EVENT.SHADOW_ORDER ADD CONSTRAINT CHK_SHADOW_STATUS CHECK (STATUS IN ('ACTIVE', 'TERMINATED_COID', 'TERMINATED_TTL', 'TERMINATED_CANCEL'))<br>CREATE INDEX BILLING_EVENT.IDX_SHADOW_ORDER_ACCT ON BILLING_EVENT.SHADOW_ORDER (ACCOUNT_ID ASC, STATUS ASC) TABLESPACE "BILLING_EVENT_DATA"<br>CREATE INDEX BILLING_EVENT.IDX_SHADOW_ORDER_TTL ON BILLING_EVENT.SHADOW_ORDER (STATUS ASC, TTL_EXPIRES_AT ASC) TABLESPACE "BILLING_EVENT_DATA"<br>COMMENT ON COLUMN BILLING_EVENT.SHADOW_ORDER.STATUS IS 'ACTIVE, TERMINATED_COID, TERMINATED_TTL, TERMINATED_CANCEL'<br>ALTER TABLE BILLING_EVENT.SHADOW_ORDER MODIFY (STATUS NOT NULL)`<br>**backup first:** CREATE TABLE BILLING_EVENT.SHADOW_ORDER_BKP66 AS SELECT SHADOW_ORDER_ID, STATUS FROM BILLING_EVENT.SHADOW_ORDER | yes | Column data is restored from SHADOW_ORDER_BKP66 (created by the -bkp changeSet).; STATUS is re-added nullable, back-filled from backup, then set NOT NULL (fails if rows were inserted after the deploy - fix them first). |
| 67 | BILLING_EVENT.SHADOW_PRODUCT_ORDER | `ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD (FREE_QUANTITY NUMBER(5) DEFAULT 0, PRODUCT_TYPE VARCHAR2(1), CHECKED_IN_STATUS VARCHAR2(1) DEFAULT 'I', CATEGORY_STATUS VARCHAR2(1) DEFAULT '2', PRODUCT_SEQUENCE NUMBER(5), CATEGORY_SEQUENCE NUMBER(3))<br>MERGE INTO BILLING_EVENT.SHADOW_PRODUCT_ORDER t USING BILLING_EVENT.SHADOW_PRODUCT_ORDER_BKP67 b ON (t.SHADOW_PRODUCT_ORDER_ID = b.SHADOW_PRODUCT_ORDER_ID) WHEN MATCHED THEN UPDATE SET t.FREE_QUANTITY = b.FREE_QUANTITY, t.PRODUCT_TYPE = b.PRODUCT_TYPE, t.CHECKED_IN_STATUS = b.CHECKED_IN_STATUS, t.CATEGORY_STATUS = b.CATEGORY_STATUS, t.PRODUCT_SEQUENCE = b.PRODUCT_SEQUENCE, t.CATEGORY_SEQUENCE = b.CATEGORY_SEQUENCE<br>ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD CONSTRAINT UK_SHADOW_SVC_SEQ UNIQUE (SHADOW_ORDER_ID, PRODUCT_SEQUENCE)<br>ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD CONSTRAINT CHK_SHADOW_SVC_TYPE CHECK (PRODUCT_TYPE IN ('R', 'T'))<br>ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER ADD CONSTRAINT CHK_SHADOW_CHECKED_IN CHECK (CHECKED_IN_STATUS IN ('I', 'A', 'D'))<br>COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.PRODUCT_TYPE IS 'R=Recurring, T=Temporary (from catalog)'<br>COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.CHECKED_IN_STATUS IS 'I=Install Pending (always for shadow), A=Active, D=Disconnect Pending'<br>COMMENT ON COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER.CATEGORY_STATUS IS '2 = Pending Connect (always for shadow orders)'`<br>**backup first:** CREATE TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER_BKP67 AS SELECT SHADOW_PRODUCT_ORDER_ID, FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE FROM BILLING_EVENT.SHADOW_PRODUCT_ORDER | yes | Column data is restored from SHADOW_PRODUCT_ORDER_BKP67 (created by the -bkp changeSet). |
| 68 | BILLING_EVENT.SHADOW_ORDER_AUDIT | `ALTER TABLE BILLING_EVENT.SHADOW_ORDER_AUDIT ADD (STATUS VARCHAR2(20))<br>MERGE INTO BILLING_EVENT.SHADOW_ORDER_AUDIT t USING BILLING_EVENT.SHADOW_ORDER_AUDIT_BKP68 b ON (t.AUDIT_ID = b.AUDIT_ID) WHEN MATCHED THEN UPDATE SET t.STATUS = b.STATUS`<br>**backup first:** CREATE TABLE BILLING_EVENT.SHADOW_ORDER_AUDIT_BKP68 AS SELECT AUDIT_ID, STATUS FROM BILLING_EVENT.SHADOW_ORDER_AUDIT | yes | Column data is restored from SHADOW_ORDER_AUDIT_BKP68 (created by the -bkp changeSet). |
| 69 | BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT | `ALTER TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT ADD (FREE_QUANTITY NUMBER(5), PRODUCT_TYPE VARCHAR2(1), CHECKED_IN_STATUS VARCHAR2(1), CATEGORY_STATUS VARCHAR2(1), PRODUCT_SEQUENCE NUMBER(5), CATEGORY_SEQUENCE NUMBER(3))<br>MERGE INTO BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT t USING BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT_BKP69 b ON (t.AUDIT_ID = b.AUDIT_ID) WHEN MATCHED THEN UPDATE SET t.FREE_QUANTITY = b.FREE_QUANTITY, t.PRODUCT_TYPE = b.PRODUCT_TYPE, t.CHECKED_IN_STATUS = b.CHECKED_IN_STATUS, t.CATEGORY_STATUS = b.CATEGORY_STATUS, t.PRODUCT_SEQUENCE = b.PRODUCT_SEQUENCE, t.CATEGORY_SEQUENCE = b.CATEGORY_SEQUENCE`<br>**backup first:** CREATE TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT_BKP69 AS SELECT AUDIT_ID, FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE FROM BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT | yes | Column data is restored from SHADOW_PRODUCT_ORDER_AUDIT_BKP69 (created by the -bkp changeSet). |
| 70 | BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT | `CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT ...` | yes | Restores the previous definition of BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT captured from baseline/earlier step. |
| 71 | BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT | `CREATE OR REPLACE TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT ...` | yes | Restores the previous definition of BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT captured from baseline/earlier step. |

Consolidated rollback script: `vibehub_1.34_Rollback/91_VIBEHUB_BILLING_EVENT_1_34_ROLLBACK.sql` (reverse order of all deploy scripts).

## 4. Risk Assessment

Overall risk: **HIGH**

CRITICAL: 0 | HIGH: 7 | MEDIUM: 31 | LOW: 12 | INFO: 0

| Severity | Code | Finding | Recommendation | Location |
|---|---|---|---|---|
| 🟧 HIGH | DML_NO_WHERE | UPDATE on BILLING_EVENT.ACCOUNT_TRANSFER has no WHERE clause - affects every row. | Confirm intent; run row-count pre-check; batch with COMMIT every N rows for big tables. | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:20 |
| 🟧 HIGH | DROP_COLUMN | Dropping STATUS from BILLING_EVENT.SHADOW_ORDER destroys data; rollback can restore structure but NOT the data. | Back up the column data (CREATE TABLE ..._BKP AS SELECT pk, cols) before deploying. | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:18 |
| 🟧 HIGH | IMPLICIT_DROPS | Also implicitly drops: CHK_SHADOW_STATUS, IDX_SHADOW_ORDER_ACCT, IDX_SHADOW_ORDER_TTL | Rollback re-creates them (generated). Check no FK relies on a dropped index. | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:18 |
| 🟧 HIGH | DROP_COLUMN | Dropping FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE from BILLING_EVENT.SHADOW_PRODUCT_ORDER destroys data; rollback can restore structure but NOT the data. | Back up the column data (CREATE TABLE ..._BKP AS SELECT pk, cols) before deploying. | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:32 |
| 🟧 HIGH | IMPLICIT_DROPS | Also implicitly drops: UK_SHADOW_SVC_SEQ, CHK_SHADOW_SVC_TYPE, CHK_SHADOW_CHECKED_IN | Rollback re-creates them (generated). Check no FK relies on a dropped index. | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:32 |
| 🟧 HIGH | DROP_COLUMN | Dropping STATUS from BILLING_EVENT.SHADOW_ORDER_AUDIT destroys data; rollback can restore structure but NOT the data. | Back up the column data (CREATE TABLE ..._BKP AS SELECT pk, cols) before deploying. | vibehub_1.34_deploy/11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:18 |
| 🟧 HIGH | DROP_COLUMN | Dropping FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE from BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT destroys data; rollback can restore structure but NOT the data. | Back up the column data (CREATE TABLE ..._BKP AS SELECT pk, cols) before deploying. | vibehub_1.34_deploy/11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:29 |
| 🟨 MEDIUM | NOLOGGING | BILLING_EVENT.SHADOW_ORDER is created NOLOGGING - direct-path loads are not written to redo and cannot be recovered from archive logs / Data Guard standby. | Take an RMAN backup after load or switch to LOGGING once loaded; confirm with DBA if FORCE LOGGING is enabled on the database. | vibehub_1.34_deploy/01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:29 |
| 🟨 MEDIUM | NOLOGGING | BILLING_EVENT.SHADOW_PRODUCT_ORDER is created NOLOGGING - direct-path loads are not written to redo and cannot be recovered from archive logs / Data Guard standby. | Take an RMAN backup after load or switch to LOGGING once loaded; confirm with DBA if FORCE LOGGING is enabled on the database. | vibehub_1.34_deploy/01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:72 |
| 🟨 MEDIUM | ON_DELETE_CASCADE | FK FK_SHADOW_SVC_ORDER uses ON DELETE CASCADE - deleting a parent row in SHADOW_ORDER silently deletes child rows. | Confirm this is intended; index the FK column to avoid full scans on parent delete. | vibehub_1.34_deploy/01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:72 |
| 🟨 MEDIUM | TRIGGER_OVERHEAD | Row-level trigger adds per-row overhead to all INSERT OR UPDATE on SHADOW_ORDER (bulk loads/batch jobs slow down). | Benchmark batch jobs; consider disabling during bulk loads. | vibehub_1.34_deploy/02_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_BEFORE_TRIG_DDL.sql:11 |
| 🟨 MEDIUM | TRIGGER_OVERHEAD | Row-level trigger adds per-row overhead to all INSERT OR UPDATE on SHADOW_PRODUCT_ORDER (bulk loads/batch jobs slow down). | Benchmark batch jobs; consider disabling during bulk loads. | vibehub_1.34_deploy/03_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_BEFORE_TRIG_DDL.sql:11 |
| 🟨 MEDIUM | TRIGGER_OVERHEAD | Row-level trigger adds per-row overhead to all INSERT OR UPDATE OR DELETE on SHADOW_ORDER (bulk loads/batch jobs slow down). | Benchmark batch jobs; consider disabling during bulk loads. | vibehub_1.34_deploy/05_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_DDL.sql:11 |
| 🟨 MEDIUM | TRIGGER_OVERHEAD | Row-level trigger adds per-row overhead to all INSERT OR UPDATE OR DELETE on SHADOW_PRODUCT_ORDER (bulk loads/batch jobs slow down). | Benchmark batch jobs; consider disabling during bulk loads. | vibehub_1.34_deploy/06_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_DDL.sql:11 |
| 🟨 MEDIUM | DROP_FK | Referential integrity enforced by FK_ACCT_TRANSFER_FROM_ACCT is removed - orphan rows can be created; re-adding it on rollback will then fail. | Rollback must clean orphans first (see generated rollback notes). | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:11 |
| 🟨 MEDIUM | SET_NULLABLE | BILLING_EVENT.ACCOUNT_TRANSFER.FROM_ACCOUNT_ID becomes nullable. Rollback (back to NOT NULL) will fail once NULL rows are written. | Rollback must clean/backfill NULL rows before re-applying NOT NULL. | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:14 |
| 🟨 MEDIUM | UPDATE_DATA | UPDATE overwrites TO_ACCOUNT_ID on BILLING_EVENT.ACCOUNT_TRANSFER; previous values are needed for rollback. | Back up affected PK + columns before deploy, or accept forward-fix only. | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:20 |
| 🟨 MEDIUM | INDEX_LOCK | CREATE INDEX on existing table ACCOUNT without ONLINE takes a table lock that blocks DML for the duration of the build. | Add ONLINE (Enterprise Edition) or deploy in a low-traffic window. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:16 |
| 🟨 MEDIUM | INDEX_LOCK | CREATE INDEX on existing table ACCOUNT_DISCOUNT without ONLINE takes a table lock that blocks DML for the duration of the build. | Add ONLINE (Enterprise Edition) or deploy in a low-traffic window. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:25 |
| 🟨 MEDIUM | INDEX_LOCK | CREATE INDEX on existing table ACCOUNT_DISCOUNT without ONLINE takes a table lock that blocks DML for the duration of the build. | Add ONLINE (Enterprise Edition) or deploy in a low-traffic window. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:34 |
| 🟨 MEDIUM | INDEX_LOCK | CREATE INDEX on existing table ACCOUNT_PRODUCT without ONLINE takes a table lock that blocks DML for the duration of the build. | Add ONLINE (Enterprise Edition) or deploy in a low-traffic window. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:43 |
| 🟨 MEDIUM | INDEX_LOCK | CREATE INDEX on existing table ACCOUNT_PRODUCT_PHONE without ONLINE takes a table lock that blocks DML for the duration of the build. | Add ONLINE (Enterprise Edition) or deploy in a low-traffic window. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:52 |
| 🟨 MEDIUM | INDEX_LOCK | CREATE INDEX on existing table ACCOUNT_PRODUCT_PHONE without ONLINE takes a table lock that blocks DML for the duration of the build. | Add ONLINE (Enterprise Edition) or deploy in a low-traffic window. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:61 |
| 🟨 MEDIUM | INDEX_LOCK | CREATE INDEX on existing table BILLTO_ADDRESS without ONLINE takes a table lock that blocks DML for the duration of the build. | Add ONLINE (Enterprise Edition) or deploy in a low-traffic window. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:70 |
| 🟨 MEDIUM | INDEX_LOCK | CREATE INDEX on existing table MASTER_ACCOUNT without ONLINE takes a table lock that blocks DML for the duration of the build. | Add ONLINE (Enterprise Edition) or deploy in a low-traffic window. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:79 |
| 🟨 MEDIUM | INDEX_LOCK | CREATE INDEX on existing table SEASONAL_ACCOUNT without ONLINE takes a table lock that blocks DML for the duration of the build. | Add ONLINE (Enterprise Edition) or deploy in a low-traffic window. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:88 |
| 🟨 MEDIUM | APP_COMPAT_DROP | Application code / ORM mappings still referencing the column will fail after deploy. | Deploy code that stops using the column first (expand/contract). | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:18 |
| 🟨 MEDIUM | APP_COMPAT_DROP | Application code / ORM mappings still referencing the column will fail after deploy. | Deploy code that stops using the column first (expand/contract). | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:32 |
| 🟨 MEDIUM | APP_COMPAT_DROP | Application code / ORM mappings still referencing the column will fail after deploy. | Deploy code that stops using the column first (expand/contract). | vibehub_1.34_deploy/11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:18 |
| 🟨 MEDIUM | APP_COMPAT_DROP | Application code / ORM mappings still referencing the column will fail after deploy. | Deploy code that stops using the column first (expand/contract). | vibehub_1.34_deploy/11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:29 |
| 🟨 MEDIUM | TRIGGER_OVERHEAD | Row-level trigger adds per-row overhead to all INSERT OR UPDATE OR DELETE on SHADOW_ORDER (bulk loads/batch jobs slow down). | Benchmark batch jobs; consider disabling during bulk loads. | vibehub_1.34_deploy/12_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql:15 |
| 🟨 MEDIUM | TRIGGER_OVERHEAD | Row-level trigger adds per-row overhead to all INSERT OR UPDATE OR DELETE on SHADOW_PRODUCT_ORDER (bulk loads/batch jobs slow down). | Benchmark batch jobs; consider disabling during bulk loads. | vibehub_1.34_deploy/13_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_ALTER_DDL.sql:17 |
| 🟨 MEDIUM | INVALID_WINDOW | TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT references STATUS and is INVALID between step 66 and its re-creation at step 70. DML on SHADOW_ORDER fails in that window (ORA-04098 for triggers). | Deploy these changeSets together in one maintenance window / same liquibase update run; quiesce application writes. | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:18 |
| 🟨 MEDIUM | INVALID_WINDOW | TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT references FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE and is INVALID between step 67 and its re-creation at step 71. DML on SHADOW_PRODUCT_ORDER fails in that window (ORA-04098 for triggers). | Deploy these changeSets together in one maintenance window / same liquibase update run; quiesce application writes. | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:32 |
| 🟨 MEDIUM | INVALID_WINDOW | TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT references STATUS and is INVALID between step 68 and its re-creation at step 70. DML on SHADOW_ORDER_AUDIT fails in that window (ORA-04098 for triggers). | Deploy these changeSets together in one maintenance window / same liquibase update run; quiesce application writes. | vibehub_1.34_deploy/11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:18 |
| 🟨 MEDIUM | INVALID_WINDOW | TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT references FREE_QUANTITY, PRODUCT_TYPE, CHECKED_IN_STATUS, CATEGORY_STATUS, PRODUCT_SEQUENCE, CATEGORY_SEQUENCE and is INVALID between step 69 and its re-creation at step 71. DML on SHADOW_PRODUCT_ORDER_AUDIT fails in that window (ORA-04098 for triggers). | Deploy these changeSets together in one maintenance window / same liquibase update run; quiesce application writes. | vibehub_1.34_deploy/11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:29 |
| 🟨 MEDIUM | FK_NO_INDEX | FK FK_SHADOW_ORDER_ACCOUNT on BILLING_EVENT.SHADOW_ORDER (ACCOUNT_ID) has no supporting index - parent DELETE/UPDATE does full scans and (Oracle) locks the child table. | CREATE INDEX IDX_SHADOW_ORDER_ACCOUNT_ID ON BILLING_EVENT.SHADOW_ORDER (ACCOUNT_ID); | BILLING_EVENT.SHADOW_ORDER |
| 🟨 MEDIUM | FK_NO_INDEX | FK FK_SHADOW_SVC_ORDER on BILLING_EVENT.SHADOW_PRODUCT_ORDER (SHADOW_ORDER_ID) has no supporting index - parent DELETE/UPDATE does full scans and (Oracle) locks the child table. | CREATE INDEX IDX_SHADOW_PRODU_SHADOW_ORDER ON BILLING_EVENT.SHADOW_PRODUCT_ORDER (SHADOW_ORDER_ID); | BILLING_EVENT.SHADOW_PRODUCT_ORDER |
| 🟦 LOW | SEQ_NOCACHE | SEQ_SHADOW_ORDER_ID is NOCACHE - every NEXTVAL updates the data dictionary; contention under high insert rates / RAC. | Use CACHE 20+ (NOORDER) unless gap-free ids are mandated. | vibehub_1.34_deploy/01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:13 |
| 🟦 LOW | SEQ_NOCACHE | SEQ_SHADOW_PRODUCT_ORDER_ID is NOCACHE - every NEXTVAL updates the data dictionary; contention under high insert rates / RAC. | Use CACHE 20+ (NOORDER) unless gap-free ids are mandated. | vibehub_1.34_deploy/01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:19 |
| 🟦 LOW | SEQ_NOCACHE | SEQ_SHADOW_ORDER_AUDIT_ID is NOCACHE - every NEXTVAL updates the data dictionary; contention under high insert rates / RAC. | Use CACHE 20+ (NOORDER) unless gap-free ids are mandated. | vibehub_1.34_deploy/04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:13 |
| 🟦 LOW | SEQ_NOCACHE | SEQ_SHADOW_PROD_ORDER_AUD_ID is NOCACHE - every NEXTVAL updates the data dictionary; contention under high insert rates / RAC. | Use CACHE 20+ (NOORDER) unless gap-free ids are mandated. | vibehub_1.34_deploy/04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:19 |
| 🟦 LOW | TRIGGER_WRITES | Trigger writes to another table (audit pattern); that table's growth/purge policy must be defined. | Add a retention/purge job for audit rows. | vibehub_1.34_deploy/05_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_DDL.sql:11 |
| 🟦 LOW | TRIGGER_WRITES | Trigger writes to another table (audit pattern); that table's growth/purge policy must be defined. | Add a retention/purge job for audit rows. | vibehub_1.34_deploy/06_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_DDL.sql:11 |
| 🟦 LOW | APP_COMPAT_ADD | Applications using SELECT * or positional INSERT on BILLING_EVENT.ACCOUNT_TRANSFER may break. | Verify no positional INSERT/SELECT * usage in application code. | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:17 |
| 🟦 LOW | DML_LOCKS | Row locks held on BILLING_EVENT.ACCOUNT_TRANSFER until COMMIT; long-running DML blocks OLTP. | Keep DML in its own changeSet; size undo; run off-peak. | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:20 |
| 🟦 LOW | VIEW_FORCE | FORCE creates the view even if it does not compile. | Post-check: view STATUS must be VALID. | vibehub_1.34_deploy/09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql:18 |
| 🟦 LOW | VIEW_COMPLEX | Complex view (9 joins / analytic functions). | Validate execution plan for main access paths after deploy. | vibehub_1.34_deploy/09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql:18 |
| 🟦 LOW | TRIGGER_WRITES | Trigger writes to another table (audit pattern); that table's growth/purge policy must be defined. | Add a retention/purge job for audit rows. | vibehub_1.34_deploy/12_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql:15 |
| 🟦 LOW | TRIGGER_WRITES | Trigger writes to another table (audit pattern); that table's growth/purge policy must be defined. | Add a retention/purge job for audit rows. | vibehub_1.34_deploy/13_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_ALTER_DDL.sql:17 |

## 5. Deployment Notes

- **Execution order** - deploy changeSets strictly in the generated order (ids are sequential; source order is preserved and checked for dependency problems - see ORDER_DEPENDENCY findings).
- **Dry run first (no DB changes):** `liquibase --changelog-file=db.changelog-SOL_SERVICES-1.34.xml validate` then `liquibase update-sql > update_preview.sql` and review the exact SQL.
- **Tag before deploy:** `liquibase tag --tag=SOL_SERVICES_1.34_PRE` (the XML changelog also contains a tagDatabase changeSet) so `liquibase rollback --tag=SOL_SERVICES_1.34_PRE` is possible.
- **Preview rollback:** `liquibase rollback-sql --tag=SOL_SERVICES_1.34_PRE` must produce SQL with no TODO/MANUAL markers.
- **House formatted-SQL package:** run deploy scripts in file-number order, then confirm all tracker rows in `LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER` are COMPLETED. Rollback package: run the `*_ROLLBACK.sql` script (forward execution) or `liquibase rollback` (inline --rollback).
- **Locking:** some DDL touches existing, possibly large tables. Deploy in a low-traffic window and set `ALTER SESSION SET DDL_LOCK_TIMEOUT = 60;` (Liquibase: add it as the first changeSet or via a session init SQL) so DDL waits for locks instead of failing with ORA-00054.
- **Invalidation window:** some code objects are INVALID between a column drop and their re-creation. Run the whole release in ONE `liquibase update` with application writes paused.
- **Data loss protection:** confirm a fresh backup (RMAN / expdp / pg_dump / mysqldump) and that the generated `-bkp` backup changeSets ran before the destructive change. Keep backup tables until the release is signed off, then drop them in a later release.
- **Application compatibility (expand/contract):** release application code that no longer reads/writes dropped columns BEFORE this database change.
- **Recompile:** after deploy run `EXEC DBMS_UTILITY.COMPILE_SCHEMA(schema => 'BILLING_EVENT', compile_all => FALSE);` and verify the invalid-objects post-check returns no new rows.
- **Optimizer statistics:** refresh stats on altered/indexed existing tables: `EXEC DBMS_STATS.GATHER_TABLE_STATS(ownname => '<SCHEMA>', tabname => '<TABLE>', cascade => TRUE);`
- **NOLOGGING objects:** inform the DBA - take a backup after initial loads; Data Guard standbys need the datafiles refreshed if non-logged loads occur (or enable FORCE LOGGING).
- **Grants/roles:** confirm target roles exist in every environment (pre-check) - missing roles fail the GRANT and halt the deployment.
- **Data migration:** DML is in separate changeSets. Compare the pre/post row counts; for >100k rows rewrite as batched PL/SQL / chunked updates to limit undo and lock time.
- **Offline guarantee:** the agent and Liquibase run locally; Liquibase resolves the dbchangelog XSD from its own jar, so no network access is required.
- **Change tracker:** `SELECT CHANGESET_ID, STATUS FROM LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER WHERE RELEASE_NUMBER = '<release label>'` - every row must be COMPLETED; a PENDING row marks the script that failed.
- **Script location:** copy the `_deploy` and `_Rollback` folders to `/opt/scripts/` (SQL_LOCATION in the tracker).

## 6. Validation Checklist

| Check | Status | Detail |
|---|---|---|
| SQL syntax | ⚠️ WARN | 1 finding(s) |
| Liquibase syntax (generated + supplied changelogs) | ✅ PASS | well-formed, ids/authors present |
| Duplicate changeSets | ✅ PASS | none |
| Rollback coverage | ✅ PASS | every changeSet has an explicit rollback |
| Naming conventions | ✅ PASS | no findings |
| Existing object conflicts | ✅ PASS | no conflicts (against supplied baseline) |
| One logical change per changeSet | ✅ PASS | XML: enforced by construction |
| DDL and DML separated | ✅ PASS | enforced by construction |
| Author naming | ✅ PASS | author = SOL_DATA |
| Sequential IDs | ✅ PASS | sequential |
| Environment-independent scripts | ✅ PASS | 1 finding(s) |
| Supplied Liquibase files (review of the input scripts) | ❌ FAIL | 36 finding(s) |

<details><summary>Validation findings</summary>

| Severity | Category | Code | Finding | Location |
|---|---|---|---|---|
| HIGH | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.1 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:3 |
| HIGH | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.4 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:3 |
| HIGH | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.5 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/05_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_DDL.sql:9 |
| HIGH | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.6 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/06_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_DDL.sql:9 |
| HIGH | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.7 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:9 |
| HIGH | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.12 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/12_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql:9 |
| HIGH | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.13 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/13_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_ALTER_DDL.sql:9 |
| MEDIUM | liquibase | LB_DDL_DML_MIX | [input changelog] changeSet SOL_SERVICES.1.34.1.0.7 mixes DDL and DML. Oracle DDL auto-commits, so a failure leaves the changeSet half-applied and not re-runnable. | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:9 |
| MEDIUM | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.2 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/02_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_BEFORE_TRIG_DDL.sql:9 |
| MEDIUM | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.3 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/03_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_BEFORE_TRIG_DDL.sql:9 |
| MEDIUM | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.8 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:9 |
| MEDIUM | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.9 has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). | vibehub_1.34_deploy/09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql:9 |
| LOW | syntax | IDENT_LONG | Identifier TRG_SHADOW_PRODUCT_ORDER_BEFORE is 31 chars (> 30) - fails on Oracle < 12.2 / COMPATIBLE < 12.2 databases. | vibehub_1.34_deploy/03_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_BEFORE_TRIG_DDL.sql:11 |
| LOW | liquibase | LB_TRACKER_IN_DDL | [input changelog] changeSet SOL_SERVICES.1.34.1.0.1 mixes tracker bookkeeping with DDL; if the DDL fails the tracker row stays PENDING and the changeSet is not re-runnable. | vibehub_1.34_deploy/01_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DDL.sql:3 |
| LOW | liquibase | LB_TRACKER_IN_DDL | [input changelog] changeSet SOL_SERVICES.1.34.1.0.4 mixes tracker bookkeeping with DDL; if the DDL fails the tracker row stays PENDING and the changeSet is not re-runnable. | vibehub_1.34_deploy/04_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_TABLES_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.2-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/02_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_BEFORE_TRIG_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.2-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/02_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_BEFORE_TRIG_DDL.sql:30 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.3-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/03_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_BEFORE_TRIG_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.3-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/03_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_BEFORE_TRIG_DDL.sql:30 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.5-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/05_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.5-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/05_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_DDL.sql:65 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.6-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/06_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.6-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/06_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_DDL.sql:73 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.7-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.7-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql:25 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.8-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.8-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/08_VIBEHUB_BILLING_EVENT_FK_INDEXES_DDL.sql:92 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.9-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.9-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/09_VIBEHUB_BILLING_EVENT_ACCOUNT_EVENT_VW_DDL.sql:130 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.10-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.10-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/10_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_DROP_COLUMNS_ALTER_DDL.sql:56 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.11-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.11-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/11_VIBEHUB_BILLING_EVENT_SHADOW_AUDIT_DROP_COLUMNS_ALTER_DDL.sql:43 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.12-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/12_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.12-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/12_VIBEHUB_BILLING_EVENT_SHADOW_ORDER_AUDIT_TRIG_ALTER_DDL.sql:67 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.13-pre has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/13_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_ALTER_DDL.sql:3 |
| LOW | rollback | RB_MISSING | [input changelog] changeSet SOL_SERVICES.1.34.1.0.13-post has no --rollback (formatted SQL never auto-generates rollbacks; `liquibase rollback` will fail here). Tracker bookkeeping changeSet. | vibehub_1.34_deploy/13_VIBEHUB_BILLING_EVENT_SHADOW_PRODUCT_ORDER_AUDIT_TRIG_ALTER_DDL.sql:67 |
| INFO | best_practice | ENV_HARDCODED_SCHEMA | Schema 'BILLING_EVENT' is hard-coded 118 time(s). |  |
| INFO | best_practice | SPLIT_DDL_DML | vibehub_1.34_deploy/07_VIBEHUB_BILLING_EVENT_ACCOUNT_TRANSFER_ALTER_DDL.sql mixes DDL and DML - the agent emitted them as separate changeSets. |  |
| INFO | best_practice | TX_REMOVED | 29 COMMIT/ROLLBACK statement(s) removed - Liquibase commits each changeSet (house tracker COMMITs are regenerated). |  |
| INFO | best_practice | TRACKER_REGENERATED | 26 existing change-tracker statement(s) ignored and regenerated with new changeSet ids. |  |

</details>

## 7. Pre-check and Post-check SQL

Run pre-checks before `liquibase update` and post-checks after. Files: `checks/precheck.sql`, `checks/postcheck.sql`.

```sql
-- PRE-DEPLOYMENT CHECKS - release 1.34 (oracle)
-- Read-only queries. Compare each result with the expected value.

-- [release] Invalid objects BEFORE deploy in BILLING_EVENT | expected: baseline (record)
SELECT OBJECT_TYPE, OBJECT_NAME, STATUS FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND STATUS <> 'VALID' ORDER BY OBJECT_TYPE, OBJECT_NAME;

-- [release] No stale Liquibase lock | expected: LOCKED = 0/false
SELECT * FROM DATABASECHANGELOGLOCK;

-- ---- step 1: CREATE_SEQUENCE BILLING_EVENT.SEQ_SHADOW_ORDER_ID
-- Sequence must not exist | expected: 0
SELECT COUNT(*) FROM DBA_SEQUENCES WHERE SEQUENCE_OWNER = 'BILLING_EVENT' AND SEQUENCE_NAME = 'SEQ_SHADOW_ORDER_ID';

-- ---- step 2: CREATE_SEQUENCE BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID
-- Sequence must not exist | expected: 0
SELECT COUNT(*) FROM DBA_SEQUENCES WHERE SEQUENCE_OWNER = 'BILLING_EVENT' AND SEQUENCE_NAME = 'SEQ_SHADOW_PRODUCT_ORDER_ID';

-- ---- step 3: CREATE_TABLE BILLING_EVENT.SHADOW_ORDER
-- BILLING_EVENT.SHADOW_ORDER must not exist yet | expected: 0
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER';
-- FK parent ACCOUNT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT';

-- ---- step 4: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_ACCT
-- Index IDX_SHADOW_ORDER_ACCT must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_ACCT';
-- Table SHADOW_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER';

-- ---- step 5: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_TTL
-- Index IDX_SHADOW_ORDER_TTL must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_TTL';
-- Table SHADOW_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER';

-- ---- step 15: CREATE_TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER
-- BILLING_EVENT.SHADOW_PRODUCT_ORDER must not exist yet | expected: 0
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER';
-- FK parent SHADOW_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER';
-- FK parent PRODUCT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'PRODUCT';

-- ---- step 16: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_SVC_PRODUCT
-- Index IDX_SHADOW_SVC_PRODUCT must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_SVC_PRODUCT';
-- Table SHADOW_PRODUCT_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER';

-- ---- step 17: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_SVC_CATEGORY
-- Index IDX_SHADOW_SVC_CATEGORY must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_SVC_CATEGORY';
-- Table SHADOW_PRODUCT_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER';

-- ---- step 32: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_BEFORE
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_ORDER_BEFORE' AND OBJECT_TYPE = 'TRIGGER';
-- Capture current source for rollback (if it exists) | expected: save output
SELECT DBMS_METADATA.GET_DDL('TRIGGER', 'TRG_SHADOW_ORDER_BEFORE', 'BILLING_EVENT') FROM DUAL;
-- Trigger table SHADOW_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER';

-- ---- step 33: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_BEFORE
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_PRODUCT_ORDER_BEFORE' AND OBJECT_TYPE = 'TRIGGER';
-- Capture current source for rollback (if it exists) | expected: save output
SELECT DBMS_METADATA.GET_DDL('TRIGGER', 'TRG_SHADOW_PRODUCT_ORDER_BEFORE', 'BILLING_EVENT') FROM DUAL;
-- Trigger table SHADOW_PRODUCT_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER';

-- ---- step 34: CREATE_SEQUENCE BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID
-- Sequence must not exist | expected: 0
SELECT COUNT(*) FROM DBA_SEQUENCES WHERE SEQUENCE_OWNER = 'BILLING_EVENT' AND SEQUENCE_NAME = 'SEQ_SHADOW_ORDER_AUDIT_ID';

-- ---- step 35: CREATE_SEQUENCE BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID
-- Sequence must not exist | expected: 0
SELECT COUNT(*) FROM DBA_SEQUENCES WHERE SEQUENCE_OWNER = 'BILLING_EVENT' AND SEQUENCE_NAME = 'SEQ_SHADOW_PROD_ORDER_AUD_ID';

-- ---- step 36: CREATE_TABLE BILLING_EVENT.SHADOW_ORDER_AUDIT
-- BILLING_EVENT.SHADOW_ORDER_AUDIT must not exist yet | expected: 0
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT';

-- ---- step 37: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_AUD_TS
-- Index IDX_SHADOW_ORDER_AUD_TS must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_AUD_TS';
-- Table SHADOW_ORDER_AUDIT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT';

-- ---- step 38: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_AUD_ID
-- Index IDX_SHADOW_ORDER_AUD_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_AUD_ID';
-- Table SHADOW_ORDER_AUDIT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT';

-- ---- step 39: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_AUD_COID
-- Index IDX_SHADOW_ORDER_AUD_COID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_AUD_COID';
-- Table SHADOW_ORDER_AUDIT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT';

-- ---- step 40: CREATE_TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT
-- BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT must not exist yet | expected: 0
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT';

-- ---- step 41: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_TS
-- Index IDX_SHADOW_PROD_ORD_AUD_TS must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_PROD_ORD_AUD_TS';
-- Table SHADOW_PRODUCT_ORDER_AUDIT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT';

-- ---- step 42: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_ID
-- Index IDX_SHADOW_PROD_ORD_AUD_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_PROD_ORD_AUD_ID';
-- Table SHADOW_PRODUCT_ORDER_AUDIT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT';

-- ---- step 43: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_SOID
-- Index IDX_SHADOW_PROD_ORD_AUD_SOID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_PROD_ORD_AUD_SOID';
-- Table SHADOW_PRODUCT_ORDER_AUDIT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT';

-- ---- step 48: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_ORDER_AUDIT' AND OBJECT_TYPE = 'TRIGGER';
-- Capture current source for rollback (if it exists) | expected: save output
SELECT DBMS_METADATA.GET_DDL('TRIGGER', 'TRG_SHADOW_ORDER_AUDIT', 'BILLING_EVENT') FROM DUAL;
-- Trigger table SHADOW_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER';

-- ---- step 49: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT' AND OBJECT_TYPE = 'TRIGGER';
-- Capture current source for rollback (if it exists) | expected: save output
SELECT DBMS_METADATA.GET_DDL('TRIGGER', 'TRG_SHADOW_PRODUCT_ORDER_AUDIT', 'BILLING_EVENT') FROM DUAL;
-- Trigger table SHADOW_PRODUCT_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER';

-- ---- step 50: DROP_CONSTRAINT BILLING_EVENT.FK_ACCT_TRANSFER_FROM_ACCT
-- FK_ACCT_TRANSFER_FROM_ACCT exists | expected: 1
SELECT COUNT(*) FROM DBA_CONSTRAINTS WHERE OWNER = 'BILLING_EVENT' AND CONSTRAINT_NAME = 'FK_ACCT_TRANSFER_FROM_ACCT';
-- Capture definition for rollback | expected: save output
SELECT DBMS_METADATA.GET_DDL('REF_CONSTRAINT', 'FK_ACCT_TRANSFER_FROM_ACCT', 'BILLING_EVENT') FROM DUAL;

-- ---- step 51: MODIFY_COLUMN BILLING_EVENT.ACCOUNT_TRANSFER
-- Current definition (rollback reference) | expected: record value
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_TRANSFER' AND COLUMN_NAME IN ('FROM_ACCOUNT_ID');
-- Dependent objects that will be invalidated | expected: review
SELECT OWNER, NAME, TYPE FROM DBA_DEPENDENCIES WHERE REFERENCED_OWNER = 'BILLING_EVENT' AND REFERENCED_NAME = 'ACCOUNT_TRANSFER' ORDER BY TYPE, NAME;

-- ---- step 52: ADD_COLUMN BILLING_EVENT.ACCOUNT_TRANSFER
-- ACCOUNT_TRANSFER.TO_ACCOUNT_ID must not exist yet | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_TRANSFER' AND COLUMN_NAME = 'TO_ACCOUNT_ID';

-- ---- step 53: UPDATE BILLING_EVENT.ACCOUNT_TRANSFER
-- Rows affected by UPDATE | expected: record value (expected volume)
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT_TRANSFER;

-- ---- step 54: CREATE_INDEX BILLING_EVENT.IDX_ACCOUNT_HOUSE_ADDR_ID
-- Index IDX_ACCOUNT_HOUSE_ADDR_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCOUNT_HOUSE_ADDR_ID';
-- Table ACCOUNT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'BILLING_EVENT' AND o.OBJECT_NAME = 'ACCOUNT';

-- ---- step 55: CREATE_INDEX BILLING_EVENT.IDX_ACCT_DISC_DISCOUNT_ID
-- Index IDX_ACCT_DISC_DISCOUNT_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_DISC_DISCOUNT_ID';
-- Table ACCOUNT_DISCOUNT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_DISCOUNT';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT_DISCOUNT;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'BILLING_EVENT' AND o.OBJECT_NAME = 'ACCOUNT_DISCOUNT';

-- ---- step 56: CREATE_INDEX BILLING_EVENT.IDX_ACCT_DISC_PRODUCT_ID
-- Index IDX_ACCT_DISC_PRODUCT_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_DISC_PRODUCT_ID';
-- Table ACCOUNT_DISCOUNT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_DISCOUNT';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT_DISCOUNT;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'BILLING_EVENT' AND o.OBJECT_NAME = 'ACCOUNT_DISCOUNT';

-- ---- step 57: CREATE_INDEX BILLING_EVENT.IDX_ACCT_PROD_PRODUCT_ID
-- Index IDX_ACCT_PROD_PRODUCT_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_PROD_PRODUCT_ID';
-- Table ACCOUNT_PRODUCT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_PRODUCT';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT_PRODUCT;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'BILLING_EVENT' AND o.OBJECT_NAME = 'ACCOUNT_PRODUCT';

-- ---- step 58: CREATE_INDEX BILLING_EVENT.IDX_ACCT_PROD_PHONE_ACCT_ID
-- Index IDX_ACCT_PROD_PHONE_ACCT_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_PROD_PHONE_ACCT_ID';
-- Table ACCOUNT_PRODUCT_PHONE exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_PRODUCT_PHONE';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT_PRODUCT_PHONE;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'BILLING_EVENT' AND o.OBJECT_NAME = 'ACCOUNT_PRODUCT_PHONE';

-- ---- step 59: CREATE_INDEX BILLING_EVENT.IDX_ACCT_PROD_PHONE_PROD_ID
-- Index IDX_ACCT_PROD_PHONE_PROD_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_PROD_PHONE_PROD_ID';
-- Table ACCOUNT_PRODUCT_PHONE exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_PRODUCT_PHONE';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT_PRODUCT_PHONE;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'BILLING_EVENT' AND o.OBJECT_NAME = 'ACCOUNT_PRODUCT_PHONE';

-- ---- step 60: CREATE_INDEX BILLING_EVENT.IDX_BILLTO_ADDR_ACCOUNT_ID
-- Index IDX_BILLTO_ADDR_ACCOUNT_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_BILLTO_ADDR_ACCOUNT_ID';
-- Table BILLTO_ADDRESS exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'BILLTO_ADDRESS';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.BILLTO_ADDRESS;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'BILLING_EVENT' AND o.OBJECT_NAME = 'BILLTO_ADDRESS';

-- ---- step 61: CREATE_INDEX BILLING_EVENT.IDX_MASTER_ACCT_MASTER_ID
-- Index IDX_MASTER_ACCT_MASTER_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_MASTER_ACCT_MASTER_ID';
-- Table MASTER_ACCOUNT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'MASTER_ACCOUNT';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.MASTER_ACCOUNT;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'BILLING_EVENT' AND o.OBJECT_NAME = 'MASTER_ACCOUNT';

-- ---- step 62: CREATE_INDEX BILLING_EVENT.IDX_SEASONAL_ACCT_ACCOUNT_ID
-- Index IDX_SEASONAL_ACCT_ACCOUNT_ID must not exist | expected: 0
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SEASONAL_ACCT_ACCOUNT_ID';
-- Table SEASONAL_ACCOUNT exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SEASONAL_ACCOUNT';
-- Table size - estimate build time | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.SEASONAL_ACCOUNT;
-- Active locks on the table (needs DBA privilege) | expected: no blocking sessions
SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID WHERE o.OWNER = 'BILLING_EVENT' AND o.OBJECT_NAME = 'SEASONAL_ACCOUNT';

-- ---- step 63: CREATE_VIEW BILLING_EVENT.ACCOUNT_EVENT_VW
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'ACCOUNT_EVENT_VW' AND OBJECT_TYPE = 'VIEW';
-- Capture current source for rollback (if it exists) | expected: save output
SELECT DBMS_METADATA.GET_DDL('VIEW', 'ACCOUNT_EVENT_VW', 'BILLING_EVENT') FROM DUAL;

-- ---- step 66: DROP_COLUMN BILLING_EVENT.SHADOW_ORDER
-- SHADOW_ORDER.STATUS exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER' AND COLUMN_NAME = 'STATUS';
-- Rows holding data that will be lost | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.SHADOW_ORDER WHERE STATUS IS NOT NULL;
-- Dependent views/triggers/PLSQL referencing the table | expected: review
SELECT OWNER, NAME, TYPE FROM DBA_DEPENDENCIES WHERE REFERENCED_OWNER = 'BILLING_EVENT' AND REFERENCED_NAME = 'SHADOW_ORDER' ORDER BY TYPE, NAME;
-- Constraints removed by CASCADE CONSTRAINTS | expected: review
SELECT c.CONSTRAINT_NAME, c.CONSTRAINT_TYPE FROM DBA_CONS_COLUMNS cc JOIN DBA_CONSTRAINTS c ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME WHERE cc.OWNER = 'BILLING_EVENT' AND cc.TABLE_NAME = 'SHADOW_ORDER' AND cc.COLUMN_NAME IN ('STATUS');
-- Indexes that Oracle drops with the column | expected: review
SELECT INDEX_NAME, COLUMN_NAME FROM DBA_IND_COLUMNS WHERE TABLE_OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER' AND COLUMN_NAME IN ('STATUS');

-- ---- step 67: DROP_COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER
-- SHADOW_PRODUCT_ORDER.FREE_QUANTITY exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'FREE_QUANTITY';
-- SHADOW_PRODUCT_ORDER.PRODUCT_TYPE exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'PRODUCT_TYPE';
-- SHADOW_PRODUCT_ORDER.CHECKED_IN_STATUS exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'CHECKED_IN_STATUS';
-- SHADOW_PRODUCT_ORDER.CATEGORY_STATUS exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'CATEGORY_STATUS';
-- SHADOW_PRODUCT_ORDER.PRODUCT_SEQUENCE exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'PRODUCT_SEQUENCE';
-- SHADOW_PRODUCT_ORDER.CATEGORY_SEQUENCE exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'CATEGORY_SEQUENCE';
-- Rows holding data that will be lost | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.SHADOW_PRODUCT_ORDER WHERE FREE_QUANTITY IS NOT NULL OR PRODUCT_TYPE IS NOT NULL OR CHECKED_IN_STATUS IS NOT NULL OR CATEGORY_STATUS IS NOT NULL OR PRODUCT_SEQUENCE IS NOT NULL OR CATEGORY_SEQUENCE IS NOT NULL;
-- Dependent views/triggers/PLSQL referencing the table | expected: review
SELECT OWNER, NAME, TYPE FROM DBA_DEPENDENCIES WHERE REFERENCED_OWNER = 'BILLING_EVENT' AND REFERENCED_NAME = 'SHADOW_PRODUCT_ORDER' ORDER BY TYPE, NAME;
-- Constraints removed by CASCADE CONSTRAINTS | expected: review
SELECT c.CONSTRAINT_NAME, c.CONSTRAINT_TYPE FROM DBA_CONS_COLUMNS cc JOIN DBA_CONSTRAINTS c ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME WHERE cc.OWNER = 'BILLING_EVENT' AND cc.TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND cc.COLUMN_NAME IN ('FREE_QUANTITY', 'PRODUCT_TYPE', 'CHECKED_IN_STATUS', 'CATEGORY_STATUS', 'PRODUCT_SEQUENCE', 'CATEGORY_SEQUENCE');
-- Indexes that Oracle drops with the column | expected: review
SELECT INDEX_NAME, COLUMN_NAME FROM DBA_IND_COLUMNS WHERE TABLE_OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME IN ('FREE_QUANTITY', 'PRODUCT_TYPE', 'CHECKED_IN_STATUS', 'CATEGORY_STATUS', 'PRODUCT_SEQUENCE', 'CATEGORY_SEQUENCE');

-- ---- step 68: DROP_COLUMN BILLING_EVENT.SHADOW_ORDER_AUDIT
-- SHADOW_ORDER_AUDIT.STATUS exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT' AND COLUMN_NAME = 'STATUS';
-- Rows holding data that will be lost | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.SHADOW_ORDER_AUDIT WHERE STATUS IS NOT NULL;
-- Dependent views/triggers/PLSQL referencing the table | expected: review
SELECT OWNER, NAME, TYPE FROM DBA_DEPENDENCIES WHERE REFERENCED_OWNER = 'BILLING_EVENT' AND REFERENCED_NAME = 'SHADOW_ORDER_AUDIT' ORDER BY TYPE, NAME;
-- Constraints removed by CASCADE CONSTRAINTS | expected: review
SELECT c.CONSTRAINT_NAME, c.CONSTRAINT_TYPE FROM DBA_CONS_COLUMNS cc JOIN DBA_CONSTRAINTS c ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME WHERE cc.OWNER = 'BILLING_EVENT' AND cc.TABLE_NAME = 'SHADOW_ORDER_AUDIT' AND cc.COLUMN_NAME IN ('STATUS');
-- Indexes that Oracle drops with the column | expected: review
SELECT INDEX_NAME, COLUMN_NAME FROM DBA_IND_COLUMNS WHERE TABLE_OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT' AND COLUMN_NAME IN ('STATUS');

-- ---- step 69: DROP_COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT
-- SHADOW_PRODUCT_ORDER_AUDIT.FREE_QUANTITY exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'FREE_QUANTITY';
-- SHADOW_PRODUCT_ORDER_AUDIT.PRODUCT_TYPE exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'PRODUCT_TYPE';
-- SHADOW_PRODUCT_ORDER_AUDIT.CHECKED_IN_STATUS exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'CHECKED_IN_STATUS';
-- SHADOW_PRODUCT_ORDER_AUDIT.CATEGORY_STATUS exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'CATEGORY_STATUS';
-- SHADOW_PRODUCT_ORDER_AUDIT.PRODUCT_SEQUENCE exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'PRODUCT_SEQUENCE';
-- SHADOW_PRODUCT_ORDER_AUDIT.CATEGORY_SEQUENCE exists | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'CATEGORY_SEQUENCE';
-- Rows holding data that will be lost | expected: record value
SELECT COUNT(*) FROM BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT WHERE FREE_QUANTITY IS NOT NULL OR PRODUCT_TYPE IS NOT NULL OR CHECKED_IN_STATUS IS NOT NULL OR CATEGORY_STATUS IS NOT NULL OR PRODUCT_SEQUENCE IS NOT NULL OR CATEGORY_SEQUENCE IS NOT NULL;
-- Dependent views/triggers/PLSQL referencing the table | expected: review
SELECT OWNER, NAME, TYPE FROM DBA_DEPENDENCIES WHERE REFERENCED_OWNER = 'BILLING_EVENT' AND REFERENCED_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' ORDER BY TYPE, NAME;
-- Constraints removed by CASCADE CONSTRAINTS | expected: review
SELECT c.CONSTRAINT_NAME, c.CONSTRAINT_TYPE FROM DBA_CONS_COLUMNS cc JOIN DBA_CONSTRAINTS c ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME WHERE cc.OWNER = 'BILLING_EVENT' AND cc.TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND cc.COLUMN_NAME IN ('FREE_QUANTITY', 'PRODUCT_TYPE', 'CHECKED_IN_STATUS', 'CATEGORY_STATUS', 'PRODUCT_SEQUENCE', 'CATEGORY_SEQUENCE');
-- Indexes that Oracle drops with the column | expected: review
SELECT INDEX_NAME, COLUMN_NAME FROM DBA_IND_COLUMNS WHERE TABLE_OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME IN ('FREE_QUANTITY', 'PRODUCT_TYPE', 'CHECKED_IN_STATUS', 'CATEGORY_STATUS', 'PRODUCT_SEQUENCE', 'CATEGORY_SEQUENCE');

-- ---- step 70: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_ORDER_AUDIT' AND OBJECT_TYPE = 'TRIGGER';
-- Capture current source for rollback (if it exists) | expected: save output
SELECT DBMS_METADATA.GET_DDL('TRIGGER', 'TRG_SHADOW_ORDER_AUDIT', 'BILLING_EVENT') FROM DUAL;
-- Trigger table SHADOW_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER';

-- ---- step 71: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT
-- Is this a replace of an existing object? | expected: 0 = new, 1 = replace
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT' AND OBJECT_TYPE = 'TRIGGER';
-- Capture current source for rollback (if it exists) | expected: save output
SELECT DBMS_METADATA.GET_DDL('TRIGGER', 'TRG_SHADOW_PRODUCT_ORDER_AUDIT', 'BILLING_EVENT') FROM DUAL;
-- Trigger table SHADOW_PRODUCT_ORDER exists | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER';
```

```sql
-- POST-DEPLOYMENT CHECKS - release 1.34 (oracle)
-- Read-only queries. Compare each result with the expected value.

-- ---- step 1: CREATE_SEQUENCE BILLING_EVENT.SEQ_SHADOW_ORDER_ID
-- Sequence created | expected: 1
SELECT COUNT(*) FROM DBA_SEQUENCES WHERE SEQUENCE_OWNER = 'BILLING_EVENT' AND SEQUENCE_NAME = 'SEQ_SHADOW_ORDER_ID';

-- ---- step 2: CREATE_SEQUENCE BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID
-- Sequence created | expected: 1
SELECT COUNT(*) FROM DBA_SEQUENCES WHERE SEQUENCE_OWNER = 'BILLING_EVENT' AND SEQUENCE_NAME = 'SEQ_SHADOW_PRODUCT_ORDER_ID';

-- ---- step 3: CREATE_TABLE BILLING_EVENT.SHADOW_ORDER
-- BILLING_EVENT.SHADOW_ORDER created | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER';
-- Column definitions as designed | expected: 12 rows
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER' AND COLUMN_NAME IN ('SHADOW_ORDER_ID', 'CUSTOMER_ORDER_ID', 'ACCOUNT_ID', 'ACCOUNT_NUMBER', 'SITE_ID', 'ORDER_TYPE', 'STATUS', 'TTL_EXPIRES_AT', 'CREATED_DT', 'CREATED_BY', 'UPDATED_DT', 'UPDATED_BY');
-- Constraints enabled | expected: all ENABLED/VALIDATED
SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE, STATUS, VALIDATED FROM DBA_CONSTRAINTS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER' ORDER BY CONSTRAINT_TYPE;
-- Grants applied | expected: expected roles
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER' ORDER BY GRANTEE;

-- ---- step 4: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_ACCT
-- Index IDX_SHADOW_ORDER_ACCT created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_ACCT';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_ACCT';

-- ---- step 5: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_TTL
-- Index IDX_SHADOW_ORDER_TTL created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_TTL';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_TTL';

-- ---- step 15: CREATE_TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER
-- BILLING_EVENT.SHADOW_PRODUCT_ORDER created | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER';
-- Column definitions as designed | expected: 16 rows
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME IN ('SHADOW_PRODUCT_ORDER_ID', 'SHADOW_ORDER_ID', 'PRODUCT_ID', 'PAID_QUANTITY', 'FREE_QUANTITY', 'CHECKED_IN_STATUS', 'OCCURRENCE_NUMBER', 'PRODUCT_TYPE', 'PRODUCT_SEQUENCE', 'CATEGORY_CODE', 'CATEGORY_STATUS', 'CATEGORY_SEQUENCE', 'CREATED_DT', 'CREATED_BY', 'UPDATED_DT', 'UPDATED_BY');
-- Constraints enabled | expected: all ENABLED/VALIDATED
SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE, STATUS, VALIDATED FROM DBA_CONSTRAINTS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' ORDER BY CONSTRAINT_TYPE;
-- Grants applied | expected: expected roles
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' ORDER BY GRANTEE;

-- ---- step 16: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_SVC_PRODUCT
-- Index IDX_SHADOW_SVC_PRODUCT created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_SVC_PRODUCT';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_SVC_PRODUCT';

-- ---- step 17: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_SVC_CATEGORY
-- Index IDX_SHADOW_SVC_CATEGORY created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_SVC_CATEGORY';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_SVC_CATEGORY';

-- ---- step 26: GRANT BILLING_EVENT.SHADOW_ORDER
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER' ORDER BY GRANTEE;

-- ---- step 27: GRANT BILLING_EVENT.SHADOW_ORDER
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER' ORDER BY GRANTEE;

-- ---- step 28: GRANT BILLING_EVENT.SHADOW_PRODUCT_ORDER
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' ORDER BY GRANTEE;

-- ---- step 29: GRANT BILLING_EVENT.SHADOW_PRODUCT_ORDER
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' ORDER BY GRANTEE;

-- ---- step 30: GRANT BILLING_EVENT.SEQ_SHADOW_ORDER_ID
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SEQ_SHADOW_ORDER_ID' ORDER BY GRANTEE;

-- ---- step 31: GRANT BILLING_EVENT.SEQ_SHADOW_PRODUCT_ORDER_ID
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SEQ_SHADOW_PRODUCT_ORDER_ID' ORDER BY GRANTEE;

-- ---- step 32: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_BEFORE
-- TRIGGER TRG_SHADOW_ORDER_BEFORE present | expected: 1
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_ORDER_BEFORE' AND OBJECT_TYPE = 'TRIGGER';
-- Compiled without errors | expected: STATUS = VALID
SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_ORDER_BEFORE';
-- No compilation errors | expected: 0 rows
SELECT TYPE, LINE, POSITION, TEXT FROM DBA_ERRORS WHERE OWNER = 'BILLING_EVENT' AND NAME = 'TRG_SHADOW_ORDER_BEFORE' ORDER BY SEQUENCE;
-- Trigger enabled | expected: ENABLED
SELECT TRIGGER_NAME, STATUS FROM DBA_TRIGGERS WHERE OWNER = 'BILLING_EVENT' AND TRIGGER_NAME = 'TRG_SHADOW_ORDER_BEFORE';

-- ---- step 33: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_BEFORE
-- TRIGGER TRG_SHADOW_PRODUCT_ORDER_BEFORE present | expected: 1
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_PRODUCT_ORDER_BEFORE' AND OBJECT_TYPE = 'TRIGGER';
-- Compiled without errors | expected: STATUS = VALID
SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_PRODUCT_ORDER_BEFORE';
-- No compilation errors | expected: 0 rows
SELECT TYPE, LINE, POSITION, TEXT FROM DBA_ERRORS WHERE OWNER = 'BILLING_EVENT' AND NAME = 'TRG_SHADOW_PRODUCT_ORDER_BEFORE' ORDER BY SEQUENCE;
-- Trigger enabled | expected: ENABLED
SELECT TRIGGER_NAME, STATUS FROM DBA_TRIGGERS WHERE OWNER = 'BILLING_EVENT' AND TRIGGER_NAME = 'TRG_SHADOW_PRODUCT_ORDER_BEFORE';

-- ---- step 34: CREATE_SEQUENCE BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID
-- Sequence created | expected: 1
SELECT COUNT(*) FROM DBA_SEQUENCES WHERE SEQUENCE_OWNER = 'BILLING_EVENT' AND SEQUENCE_NAME = 'SEQ_SHADOW_ORDER_AUDIT_ID';

-- ---- step 35: CREATE_SEQUENCE BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID
-- Sequence created | expected: 1
SELECT COUNT(*) FROM DBA_SEQUENCES WHERE SEQUENCE_OWNER = 'BILLING_EVENT' AND SEQUENCE_NAME = 'SEQ_SHADOW_PROD_ORDER_AUD_ID';

-- ---- step 36: CREATE_TABLE BILLING_EVENT.SHADOW_ORDER_AUDIT
-- BILLING_EVENT.SHADOW_ORDER_AUDIT created | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT';
-- Column definitions as designed | expected: 16 rows
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT' AND COLUMN_NAME IN ('AUDIT_ID', 'AUDIT_TIMESTAMP', 'AUDIT_ACTION', 'AUDIT_TRANSACTION_ID', 'SHADOW_ORDER_ID', 'CUSTOMER_ORDER_ID', 'ACCOUNT_ID', 'ACCOUNT_NUMBER', 'SITE_ID', 'ORDER_TYPE', 'STATUS', 'TTL_EXPIRES_AT', 'CREATED_DT', 'CREATED_BY', 'UPDATED_DT', 'UPDATED_BY');
-- Constraints enabled | expected: all ENABLED/VALIDATED
SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE, STATUS, VALIDATED FROM DBA_CONSTRAINTS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT' ORDER BY CONSTRAINT_TYPE;
-- Grants applied | expected: expected roles
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT' ORDER BY GRANTEE;

-- ---- step 37: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_AUD_TS
-- Index IDX_SHADOW_ORDER_AUD_TS created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_AUD_TS';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_AUD_TS';

-- ---- step 38: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_AUD_ID
-- Index IDX_SHADOW_ORDER_AUD_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_AUD_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_AUD_ID';

-- ---- step 39: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_ORDER_AUD_COID
-- Index IDX_SHADOW_ORDER_AUD_COID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_AUD_COID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_ORDER_AUD_COID';

-- ---- step 40: CREATE_TABLE BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT
-- BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT created | expected: 1
SELECT COUNT(*) FROM DBA_TABLES WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT';
-- Column definitions as designed | expected: 20 rows
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME IN ('AUDIT_ID', 'AUDIT_TIMESTAMP', 'AUDIT_ACTION', 'AUDIT_TRANSACTION_ID', 'SHADOW_PRODUCT_ORDER_ID', 'SHADOW_ORDER_ID', 'PRODUCT_ID', 'PAID_QUANTITY', 'FREE_QUANTITY', 'CHECKED_IN_STATUS', 'OCCURRENCE_NUMBER', 'PRODUCT_TYPE', 'PRODUCT_SEQUENCE', 'CATEGORY_CODE', 'CATEGORY_STATUS', 'CATEGORY_SEQUENCE', 'CREATED_DT', 'CREATED_BY', 'UPDATED_DT', 'UPDATED_BY');
-- Constraints enabled | expected: all ENABLED/VALIDATED
SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE, STATUS, VALIDATED FROM DBA_CONSTRAINTS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' ORDER BY CONSTRAINT_TYPE;
-- Grants applied | expected: expected roles
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' ORDER BY GRANTEE;

-- ---- step 41: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_TS
-- Index IDX_SHADOW_PROD_ORD_AUD_TS created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_PROD_ORD_AUD_TS';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_PROD_ORD_AUD_TS';

-- ---- step 42: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_ID
-- Index IDX_SHADOW_PROD_ORD_AUD_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_PROD_ORD_AUD_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_PROD_ORD_AUD_ID';

-- ---- step 43: CREATE_INDEX BILLING_EVENT.IDX_SHADOW_PROD_ORD_AUD_SOID
-- Index IDX_SHADOW_PROD_ORD_AUD_SOID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_PROD_ORD_AUD_SOID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SHADOW_PROD_ORD_AUD_SOID';

-- ---- step 44: GRANT BILLING_EVENT.SHADOW_ORDER_AUDIT
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT' ORDER BY GRANTEE;

-- ---- step 45: GRANT BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' ORDER BY GRANTEE;

-- ---- step 46: GRANT BILLING_EVENT.SEQ_SHADOW_ORDER_AUDIT_ID
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SEQ_SHADOW_ORDER_AUDIT_ID' ORDER BY GRANTEE;

-- ---- step 47: GRANT BILLING_EVENT.SEQ_SHADOW_PROD_ORDER_AUD_ID
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'SEQ_SHADOW_PROD_ORDER_AUD_ID' ORDER BY GRANTEE;

-- ---- step 48: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
-- TRIGGER TRG_SHADOW_ORDER_AUDIT present | expected: 1
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_ORDER_AUDIT' AND OBJECT_TYPE = 'TRIGGER';
-- Compiled without errors | expected: STATUS = VALID
SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_ORDER_AUDIT';
-- No compilation errors | expected: 0 rows
SELECT TYPE, LINE, POSITION, TEXT FROM DBA_ERRORS WHERE OWNER = 'BILLING_EVENT' AND NAME = 'TRG_SHADOW_ORDER_AUDIT' ORDER BY SEQUENCE;
-- Trigger enabled | expected: ENABLED
SELECT TRIGGER_NAME, STATUS FROM DBA_TRIGGERS WHERE OWNER = 'BILLING_EVENT' AND TRIGGER_NAME = 'TRG_SHADOW_ORDER_AUDIT';

-- ---- step 49: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT
-- TRIGGER TRG_SHADOW_PRODUCT_ORDER_AUDIT present | expected: 1
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT' AND OBJECT_TYPE = 'TRIGGER';
-- Compiled without errors | expected: STATUS = VALID
SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT';
-- No compilation errors | expected: 0 rows
SELECT TYPE, LINE, POSITION, TEXT FROM DBA_ERRORS WHERE OWNER = 'BILLING_EVENT' AND NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT' ORDER BY SEQUENCE;
-- Trigger enabled | expected: ENABLED
SELECT TRIGGER_NAME, STATUS FROM DBA_TRIGGERS WHERE OWNER = 'BILLING_EVENT' AND TRIGGER_NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT';

-- ---- step 50: DROP_CONSTRAINT BILLING_EVENT.FK_ACCT_TRANSFER_FROM_ACCT
-- FK_ACCT_TRANSFER_FROM_ACCT dropped | expected: 0
SELECT COUNT(*) FROM DBA_CONSTRAINTS WHERE OWNER = 'BILLING_EVENT' AND CONSTRAINT_NAME = 'FK_ACCT_TRANSFER_FROM_ACCT';

-- ---- step 51: MODIFY_COLUMN BILLING_EVENT.ACCOUNT_TRANSFER
-- New definition applied | expected: as designed
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_TRANSFER' AND COLUMN_NAME IN ('FROM_ACCOUNT_ID');

-- ---- step 52: ADD_COLUMN BILLING_EVENT.ACCOUNT_TRANSFER
-- ACCOUNT_TRANSFER.TO_ACCOUNT_ID added | expected: 1
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_TRANSFER' AND COLUMN_NAME = 'TO_ACCOUNT_ID';
-- New column definition | expected: as designed
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_TRANSFER' AND COLUMN_NAME IN ('TO_ACCOUNT_ID');

-- ---- step 53: UPDATE BILLING_EVENT.ACCOUNT_TRANSFER
-- Rows still matching predicate | expected: same as pre-check
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT_TRANSFER;
-- Total row count | expected: pre-count +/- expected delta
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT_TRANSFER;

-- ---- step 54: CREATE_INDEX BILLING_EVENT.IDX_ACCOUNT_HOUSE_ADDR_ID
-- Index IDX_ACCOUNT_HOUSE_ADDR_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCOUNT_HOUSE_ADDR_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCOUNT_HOUSE_ADDR_ID';

-- ---- step 55: CREATE_INDEX BILLING_EVENT.IDX_ACCT_DISC_DISCOUNT_ID
-- Index IDX_ACCT_DISC_DISCOUNT_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_DISC_DISCOUNT_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_DISC_DISCOUNT_ID';

-- ---- step 56: CREATE_INDEX BILLING_EVENT.IDX_ACCT_DISC_PRODUCT_ID
-- Index IDX_ACCT_DISC_PRODUCT_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_DISC_PRODUCT_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_DISC_PRODUCT_ID';

-- ---- step 57: CREATE_INDEX BILLING_EVENT.IDX_ACCT_PROD_PRODUCT_ID
-- Index IDX_ACCT_PROD_PRODUCT_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_PROD_PRODUCT_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_PROD_PRODUCT_ID';

-- ---- step 58: CREATE_INDEX BILLING_EVENT.IDX_ACCT_PROD_PHONE_ACCT_ID
-- Index IDX_ACCT_PROD_PHONE_ACCT_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_PROD_PHONE_ACCT_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_PROD_PHONE_ACCT_ID';

-- ---- step 59: CREATE_INDEX BILLING_EVENT.IDX_ACCT_PROD_PHONE_PROD_ID
-- Index IDX_ACCT_PROD_PHONE_PROD_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_PROD_PHONE_PROD_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_ACCT_PROD_PHONE_PROD_ID';

-- ---- step 60: CREATE_INDEX BILLING_EVENT.IDX_BILLTO_ADDR_ACCOUNT_ID
-- Index IDX_BILLTO_ADDR_ACCOUNT_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_BILLTO_ADDR_ACCOUNT_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_BILLTO_ADDR_ACCOUNT_ID';

-- ---- step 61: CREATE_INDEX BILLING_EVENT.IDX_MASTER_ACCT_MASTER_ID
-- Index IDX_MASTER_ACCT_MASTER_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_MASTER_ACCT_MASTER_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_MASTER_ACCT_MASTER_ID';

-- ---- step 62: CREATE_INDEX BILLING_EVENT.IDX_SEASONAL_ACCT_ACCOUNT_ID
-- Index IDX_SEASONAL_ACCT_ACCOUNT_ID created | expected: 1
SELECT COUNT(*) FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SEASONAL_ACCT_ACCOUNT_ID';
-- Index usable | expected: STATUS = VALID
SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM DBA_INDEXES WHERE OWNER = 'BILLING_EVENT' AND INDEX_NAME = 'IDX_SEASONAL_ACCT_ACCOUNT_ID';

-- ---- step 63: CREATE_VIEW BILLING_EVENT.ACCOUNT_EVENT_VW
-- VIEW ACCOUNT_EVENT_VW present | expected: 1
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'ACCOUNT_EVENT_VW' AND OBJECT_TYPE = 'VIEW';
-- Compiled without errors | expected: STATUS = VALID
SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'ACCOUNT_EVENT_VW';
-- No compilation errors | expected: 0 rows
SELECT TYPE, LINE, POSITION, TEXT FROM DBA_ERRORS WHERE OWNER = 'BILLING_EVENT' AND NAME = 'ACCOUNT_EVENT_VW' ORDER BY SEQUENCE;
-- View is queryable | expected: executes
SELECT COUNT(*) FROM BILLING_EVENT.ACCOUNT_EVENT_VW WHERE 1 = 0;

-- ---- step 65: GRANT BILLING_EVENT.ACCOUNT_EVENT_VW
-- Privileges | expected: grantees listed
SELECT GRANTEE, PRIVILEGE FROM DBA_TAB_PRIVS WHERE TABLE_SCHEMA = 'BILLING_EVENT' AND TABLE_NAME = 'ACCOUNT_EVENT_VW' ORDER BY GRANTEE;

-- ---- step 66: DROP_COLUMN BILLING_EVENT.SHADOW_ORDER
-- SHADOW_ORDER.STATUS dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER' AND COLUMN_NAME = 'STATUS';

-- ---- step 67: DROP_COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER
-- SHADOW_PRODUCT_ORDER.FREE_QUANTITY dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'FREE_QUANTITY';
-- SHADOW_PRODUCT_ORDER.PRODUCT_TYPE dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'PRODUCT_TYPE';
-- SHADOW_PRODUCT_ORDER.CHECKED_IN_STATUS dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'CHECKED_IN_STATUS';
-- SHADOW_PRODUCT_ORDER.CATEGORY_STATUS dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'CATEGORY_STATUS';
-- SHADOW_PRODUCT_ORDER.PRODUCT_SEQUENCE dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'PRODUCT_SEQUENCE';
-- SHADOW_PRODUCT_ORDER.CATEGORY_SEQUENCE dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER' AND COLUMN_NAME = 'CATEGORY_SEQUENCE';

-- ---- step 68: DROP_COLUMN BILLING_EVENT.SHADOW_ORDER_AUDIT
-- SHADOW_ORDER_AUDIT.STATUS dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_ORDER_AUDIT' AND COLUMN_NAME = 'STATUS';

-- ---- step 69: DROP_COLUMN BILLING_EVENT.SHADOW_PRODUCT_ORDER_AUDIT
-- SHADOW_PRODUCT_ORDER_AUDIT.FREE_QUANTITY dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'FREE_QUANTITY';
-- SHADOW_PRODUCT_ORDER_AUDIT.PRODUCT_TYPE dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'PRODUCT_TYPE';
-- SHADOW_PRODUCT_ORDER_AUDIT.CHECKED_IN_STATUS dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'CHECKED_IN_STATUS';
-- SHADOW_PRODUCT_ORDER_AUDIT.CATEGORY_STATUS dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'CATEGORY_STATUS';
-- SHADOW_PRODUCT_ORDER_AUDIT.PRODUCT_SEQUENCE dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'PRODUCT_SEQUENCE';
-- SHADOW_PRODUCT_ORDER_AUDIT.CATEGORY_SEQUENCE dropped | expected: 0
SELECT COUNT(*) FROM DBA_TAB_COLUMNS WHERE OWNER = 'BILLING_EVENT' AND TABLE_NAME = 'SHADOW_PRODUCT_ORDER_AUDIT' AND COLUMN_NAME = 'CATEGORY_SEQUENCE';

-- ---- step 70: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_ORDER_AUDIT
-- TRIGGER TRG_SHADOW_ORDER_AUDIT present | expected: 1
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_ORDER_AUDIT' AND OBJECT_TYPE = 'TRIGGER';
-- Compiled without errors | expected: STATUS = VALID
SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_ORDER_AUDIT';
-- No compilation errors | expected: 0 rows
SELECT TYPE, LINE, POSITION, TEXT FROM DBA_ERRORS WHERE OWNER = 'BILLING_EVENT' AND NAME = 'TRG_SHADOW_ORDER_AUDIT' ORDER BY SEQUENCE;
-- Trigger enabled | expected: ENABLED
SELECT TRIGGER_NAME, STATUS FROM DBA_TRIGGERS WHERE OWNER = 'BILLING_EVENT' AND TRIGGER_NAME = 'TRG_SHADOW_ORDER_AUDIT';

-- ---- step 71: CREATE_TRIGGER BILLING_EVENT.TRG_SHADOW_PRODUCT_ORDER_AUDIT
-- TRIGGER TRG_SHADOW_PRODUCT_ORDER_AUDIT present | expected: 1
SELECT COUNT(*) FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT' AND OBJECT_TYPE = 'TRIGGER';
-- Compiled without errors | expected: STATUS = VALID
SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND OBJECT_NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT';
-- No compilation errors | expected: 0 rows
SELECT TYPE, LINE, POSITION, TEXT FROM DBA_ERRORS WHERE OWNER = 'BILLING_EVENT' AND NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT' ORDER BY SEQUENCE;
-- Trigger enabled | expected: ENABLED
SELECT TRIGGER_NAME, STATUS FROM DBA_TRIGGERS WHERE OWNER = 'BILLING_EVENT' AND TRIGGER_NAME = 'TRG_SHADOW_PRODUCT_ORDER_AUDIT';

-- [release] Invalid objects in BILLING_EVENT | expected: 0 rows (or same as before deploy)
SELECT OBJECT_TYPE, OBJECT_NAME, STATUS FROM DBA_OBJECTS WHERE OWNER = 'BILLING_EVENT' AND STATUS <> 'VALID' ORDER BY OBJECT_TYPE, OBJECT_NAME;

-- [release] Liquibase history | expected: release changeSets EXECUTED
SELECT ID, AUTHOR, FILENAME, DATEEXECUTED, EXECTYPE FROM DATABASECHANGELOG ORDER BY ORDEREXECUTED DESC FETCH FIRST 30 ROWS ONLY;

-- [release] Change tracker status | expected: all COMPLETED
SELECT CHANGESET_ID, SCRIPT_NAME, STATUS, COUNT_BEFORE_CHANGE, COUNT_AFTER_CHANGE FROM LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER WHERE RELEASE_NUMBER = 'SOL_SERVICES 1.34' ORDER BY CHANGESET_ID;
```
