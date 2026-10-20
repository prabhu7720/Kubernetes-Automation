--liquibase formatted sql

--changeset agent:006
--comment: Insert - DEPARTMENT

INSERT INTO HR.DEPARTMENT (DEPARTMENT_ID, DEPT_CODE, DEPT_NAME) VALUES (1, 'IT', 'Information Technology');

COMMIT;

--rollback DELETE FROM HR.DEPARTMENT WHERE DEPARTMENT_ID = 1;
