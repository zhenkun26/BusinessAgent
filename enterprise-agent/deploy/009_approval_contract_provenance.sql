-- Managed v9: immutable approval provenance; managed v8 remains C10 session fencing.
-- The runner owns the transaction: DDL and ledger commit or roll back together.
-- Stop/drain old executors first. Never backfill or certify legacy approval rows.
-- Existing standalone 009 installations are verified exactly, never repaired.

SET LOCAL search_path TO pg_catalog;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
LOCK TABLE public.approval_requests IN ACCESS EXCLUSIVE MODE;

DO $migration$
DECLARE
    relation_oid oid := 'public.approval_requests'::regclass;
    installing boolean;
    column_number smallint;
    item record;
    actual record;
    routine_count integer;
    guard_oid oid;
    shape_source text := $shape$
SELECT CASE
    WHEN contract IS NULL THEN TRUE
    WHEN jsonb_typeof(contract) <> 'object' THEN FALSE
    ELSE COALESCE(
        contract ?& ARRAY['version', 'approval_id', 'session_id', 'requester_id',
            'operation_type', 'risk_level', 'created_at', 'expires_at',
            'tool_calls', 'approver_roles', 'targets']
        AND contract - ARRAY['version', 'approval_id', 'session_id', 'requester_id',
            'operation_type', 'risk_level', 'created_at', 'expires_at',
            'tool_calls', 'approver_roles', 'targets'] = '{}'::jsonb
        AND contract ->> 'version' = 'utc-human-v2'
        AND jsonb_typeof(contract -> 'approval_id') = 'string'
        AND jsonb_typeof(contract -> 'session_id') = 'string'
        AND jsonb_typeof(contract -> 'requester_id') = 'string'
        AND jsonb_typeof(contract -> 'operation_type') = 'string'
        AND jsonb_typeof(contract -> 'risk_level') = 'string'
        AND jsonb_typeof(contract -> 'created_at') = 'string'
        AND jsonb_typeof(contract -> 'expires_at') = 'string'
        AND jsonb_typeof(contract -> 'tool_calls') = 'array'
        AND jsonb_typeof(contract -> 'approver_roles') = 'array'
        AND jsonb_typeof(contract -> 'targets') = 'array', FALSE)
END;
$shape$;
    guard_source text := $guard$
BEGIN
    IF OLD.approval_contract IS DISTINCT FROM NEW.approval_contract THEN
        RAISE EXCEPTION USING ERRCODE = '23514',
            MESSAGE = 'APPROVAL_CONTRACT_IMMUTABLE';
    END IF;
    RETURN NEW;
END;
$guard$;
BEGIN
    IF (SELECT relkind FROM pg_class WHERE oid = relation_oid) <> 'r'
       OR EXISTS (SELECT 1 FROM pg_inherits
                  WHERE inhrelid = relation_oid OR inhparent = relation_oid) THEN
        RAISE EXCEPTION 'APPROVAL_CONTRACT_TABLE_UNSUPPORTED';
    END IF;
    installing := NOT EXISTS (
        SELECT 1 FROM pg_attribute WHERE attrelid = relation_oid
        AND attname = 'approval_contract' AND NOT attisdropped);
    IF installing THEN
        IF EXISTS (SELECT 1 FROM pg_proc WHERE pronamespace = 'public'::regnamespace
                   AND proname IN ('approval_contract_v2_shape', 'approval_contract_v2_immutable'))
           OR EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = relation_oid
                      AND conname = 'approval_contract_v2_shape_check')
           OR EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid = relation_oid
                      AND tgname = 'approval_contract_v2_immutable') THEN
            RAISE EXCEPTION 'APPROVAL_CONTRACT_PARTIAL_INSTALLATION';
        END IF;
        ALTER TABLE public.approval_requests ADD COLUMN approval_contract JSONB DEFAULT NULL;
    END IF;

    SELECT a.*, pg_get_expr(d.adbin, d.adrelid) AS default_expression INTO actual
    FROM pg_attribute a LEFT JOIN pg_attrdef d
        ON d.adrelid = a.attrelid AND d.adnum = a.attnum
    WHERE a.attrelid = relation_oid AND a.attname = 'approval_contract' AND NOT a.attisdropped;
    IF NOT FOUND OR actual.atttypid <> 'jsonb'::regtype OR actual.atttypmod <> -1
       OR actual.attnotnull OR actual.attidentity <> '' OR actual.attgenerated <> ''
       OR actual.attinhcount <> 0 OR NOT actual.attislocal
       OR (actual.default_expression IS NOT NULL AND actual.default_expression <> 'NULL::jsonb') THEN
        RAISE EXCEPTION 'APPROVAL_CONTRACT_COLUMN_DRIFT';
    END IF;
    column_number := actual.attnum;

    FOR item IN SELECT * FROM (VALUES
        ('approval_contract_v2_shape', 'contract jsonb', 'boolean', 'sql',
         'IMMUTABLE', 'SAFE', 'i', 's', shape_source),
        ('approval_contract_v2_immutable', '', 'trigger', 'plpgsql',
         'VOLATILE', 'UNSAFE', 'v', 'u', guard_source)
    ) AS expected(name, arguments, result_type, language, volatility, parallel,
                  volatility_code, parallel_code, source)
    LOOP
        SELECT count(*) INTO routine_count FROM pg_proc
        WHERE pronamespace = 'public'::regnamespace AND proname = item.name;
        IF installing THEN
            -- The namespace was checked before any new objects were added.
            IF routine_count <> 0 THEN
                RAISE EXCEPTION 'APPROVAL_CONTRACT_FUNCTION_COLLISION';
            END IF;
            EXECUTE format('CREATE FUNCTION public.%I(%s) RETURNS %s LANGUAGE %I %s '
                'PARALLEL %s CALLED ON NULL INPUT SECURITY INVOKER '
                'SET search_path TO pg_catalog AS %L', item.name, item.arguments,
                item.result_type, item.language, item.volatility, item.parallel, item.source);
        ELSIF routine_count <> 1 THEN
            RAISE EXCEPTION 'APPROVAL_CONTRACT_FUNCTION_MISSING_OR_OVERLOADED';
        END IF;
        SELECT p.*, l.lanname INTO actual FROM pg_proc p
        JOIN pg_language l ON l.oid = p.prolang
        WHERE p.pronamespace = 'public'::regnamespace AND p.proname = item.name;
        IF NOT FOUND OR pg_get_function_identity_arguments(actual.oid) <> item.arguments
           OR pg_get_function_result(actual.oid) <> item.result_type
           OR actual.lanname <> item.language OR actual.prosrc <> item.source
           OR actual.prokind <> 'f' OR actual.prosecdef OR actual.proleakproof
           OR actual.proisstrict OR actual.proretset OR actual.provariadic <> 0
           OR actual.prosupport <> 0 OR actual.pronargdefaults <> 0
           OR actual.proargdefaults IS NOT NULL OR actual.proallargtypes IS NOT NULL
           OR actual.proargmodes IS NOT NULL OR actual.probin IS NOT NULL
           OR actual.prosqlbody IS NOT NULL
           OR actual.provolatile::text <> item.volatility_code
           OR actual.proparallel::text <> item.parallel_code
           OR actual.proconfig IS DISTINCT FROM ARRAY['search_path=pg_catalog']::text[] THEN
            RAISE EXCEPTION 'APPROVAL_CONTRACT_FUNCTION_DRIFT';
        END IF;
        IF item.name = 'approval_contract_v2_immutable' THEN guard_oid := actual.oid;
        END IF;
    END LOOP;

    IF installing THEN
        ALTER TABLE public.approval_requests ADD CONSTRAINT approval_contract_v2_shape_check
            CHECK (public.approval_contract_v2_shape(approval_contract));
        -- AFTER UPDATE catches even contract changes made by a BEFORE trigger.
        -- Fire on every UPDATE, not only statements explicitly mentioning the column.
        CREATE TRIGGER approval_contract_v2_immutable AFTER UPDATE ON public.approval_requests
            FOR EACH ROW EXECUTE FUNCTION public.approval_contract_v2_immutable();
        ALTER TABLE public.approval_requests ENABLE ALWAYS TRIGGER approval_contract_v2_immutable;
    END IF;

    SELECT * INTO actual FROM pg_constraint WHERE conrelid = relation_oid
        AND conname = 'approval_contract_v2_shape_check';
    IF NOT FOUND OR actual.contype <> 'c' OR NOT actual.convalidated
       OR actual.condeferrable OR actual.condeferred OR NOT actual.conislocal
       OR actual.coninhcount <> 0 OR actual.connoinherit OR actual.conparentid <> 0
       OR actual.conkey IS DISTINCT FROM ARRAY[column_number]::smallint[]
       OR pg_get_expr(actual.conbin, actual.conrelid) IS DISTINCT FROM
          'public.approval_contract_v2_shape(approval_contract)' THEN
        RAISE EXCEPTION 'APPROVAL_CONTRACT_CHECK_DRIFT';
    END IF;
    SELECT * INTO actual FROM pg_trigger WHERE tgrelid = relation_oid
        AND tgname = 'approval_contract_v2_immutable';
    IF NOT FOUND OR actual.tgfoid <> guard_oid OR actual.tgtype <> 17
       OR actual.tgenabled <> 'A' OR actual.tgisinternal OR actual.tgparentid <> 0
       OR actual.tgconstraint <> 0 OR actual.tgconstrrelid <> 0 OR actual.tgconstrindid <> 0
       OR actual.tgdeferrable OR actual.tginitdeferred OR actual.tgnargs <> 0
       OR actual.tgattr::text <> '' OR actual.tgargs <> ''::bytea
       OR actual.tgqual IS NOT NULL OR actual.tgoldtable IS NOT NULL
       OR actual.tgnewtable IS NOT NULL THEN
        RAISE EXCEPTION 'APPROVAL_CONTRACT_TRIGGER_DRIFT';
    END IF;
END;
$migration$;
