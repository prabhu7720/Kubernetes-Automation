--liquibase formatted sql

--changeset agent:001
--comment: Create Table - employee

CREATE TABLE employee (
    employee_id NUMBER PRIMARY KEY,
    employee_name VARCHAR2(100),
    created_date DATE
);

--rollback DROP TABLE employee CASCADE CONSTRAINTS;
