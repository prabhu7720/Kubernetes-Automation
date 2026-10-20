--liquibase formatted sql

--changeset agent:005 splitStatements:false
--comment: Create Procedure - PRC_ASSIGN_DEPARTMENT

CREATE OR REPLACE PROCEDURE HR.PRC_ASSIGN_DEPARTMENT (p_emp_id IN NUMBER, p_dept_id IN NUMBER) AS
BEGIN
    UPDATE HR.EMPLOYEE SET DEPARTMENT_ID = p_dept_id WHERE EMPLOYEE_ID = p_emp_id;
    IF SQL%ROWCOUNT = 0 THEN
        RAISE_APPLICATION_ERROR(-20001, 'Employee not found');
    END IF;
END PRC_ASSIGN_DEPARTMENT;

--rollback DROP PROCEDURE HR.PRC_ASSIGN_DEPARTMENT
--rollback /
