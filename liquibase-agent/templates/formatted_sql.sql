-- @template sql_file_header
--liquibase formatted sql

-- @template sql_changeset
--changeset ${author}:${id}${attrs}
-- @template tracker_insert
Insert Into ${tracker_table} (CHANGESET_ID,SCHEMA_NAME,SCRIPT_NAME,RELEASE_NUMBER,OBJECT_TYPE,OBJECT_NAME,SQL_LOCATION,ACTION,STATUS,COUNT_BEFORE_CHANGE,COUNT_AFTER_CHANGE,ROLLBACK_FLAG) VALUES ('${changeset_id}','${schema}','${script_name}','${release_label}','${object_type}','${object_name}','${sql_location}','${action}','PENDING',(${count_sql}),0,${rollback_flag});
-- @template tracker_update
UPDATE ${tracker_table} SET COUNT_AFTER_CHANGE = (${count_sql}), STATUS = 'COMPLETED' WHERE CHANGESET_ID = '${changeset_id}';
-- @template tracker_insert_rollback
--rollback DELETE FROM ${tracker_table} WHERE CHANGESET_ID = '${changeset_id}';
-- @template tracker_update_rollback
--rollback UPDATE ${tracker_table} SET STATUS = 'ROLLED_BACK', ROLLBACK_FLAG = 1 WHERE CHANGESET_ID = '${changeset_id}';
-- @template banner
-- =====================================================
${lines}
-- =====================================================
