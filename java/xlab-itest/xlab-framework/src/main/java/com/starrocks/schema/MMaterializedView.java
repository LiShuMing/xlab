package com.starrocks.schema;

import com.google.common.base.Strings;
import com.google.common.collect.Lists;

import java.util.List;

public class MMaterializedView extends MTable {
    // mv's columns are derived from the defined query rather than user's settings.
    private final static List<String> MV_COLUMNS = Lists.newArrayList();
    private final static List<String> MV_PART_KEYS = Lists.newArrayList();
    private final static String MV_DUPLICATE_KEY = "";

    private final String definedQuery;
    private String orderKeys;
    private String refreshSchema;
    private String refreshActions;
    private List<String> mvProperties;
    private boolean isMinified = true;
    private String partColumnType = "";

    public MMaterializedView(String tableName, String definedQuery) {
        super(tableName, MV_COLUMNS);
        this.definedQuery = definedQuery;
    }

    public MMaterializedView(String tableName, String partCol, String definedQuery) {
        super(tableName, "", MV_COLUMNS, partCol, MV_COLUMNS);
        this.definedQuery = definedQuery;
    }

    public MMaterializedView(String tableName, String distCol, String partCol, String definedQuery) {
        super(tableName, distCol, MV_COLUMNS, partCol, MV_PART_KEYS);
        this.definedQuery = definedQuery;
    }

    public MMaterializedView(String tableName, String distCol, String partCol, String orderKeys, String definedQuery) {
        super(tableName, distCol, MV_COLUMNS, partCol, MV_PART_KEYS, MV_DUPLICATE_KEY);
        this.definedQuery = definedQuery;
        this.orderKeys = orderKeys;
    }

    public MMaterializedView withRefreshSchema(String refreshSchema) {
        this.refreshSchema = refreshSchema;
        return this;
    }
    public MMaterializedView withRefreshActions(String refreshActions) {
        this.refreshActions = refreshActions;
        return this;
    }
    public MMaterializedView withMVProperties(List<String> mvProperties) {
        this.mvProperties = mvProperties;
        return this;
    }

    public String getDefinedQuery() {
        return definedQuery;
    }

    public String getOrderKeys() {
        return orderKeys;
    }

    public String getRefreshSchema() {
        return refreshSchema;
    }

    public String getRefreshActions() {
        return refreshActions;
    }

    public List<String> getMvProperties() {
        return mvProperties;
    }
    private void withMinified(boolean isMinified) {
        this.isMinified = isMinified;
    }
    public boolean isMinified() {
        return isMinified;
    }

    public String getPartColumnType() {
        return partColumnType;
    }

    public MMaterializedView withPartColumnType(String partColumnType) {
        this.partColumnType = partColumnType;
        return this;
    }

    @Override
    public String getCreateTableSql() {
        String sql = String.format("CREATE MATERIALIZED VIEW if not exists %s \n", tableName);
        if (!Strings.isNullOrEmpty(partCol)) {
            sql += String.format("PARTITION BY %s \n", partCol);
        }
        if (Strings.isNullOrEmpty(this.distCol)) {
            sql += "DISTRIBUTED BY RANDOM \n";
        } else {
            sql += String.format("DISTRIBUTED BY '%s' \n", distCol);
        }
        if (Strings.isNullOrEmpty(this.refreshSchema)) {
            sql += "REFRESH DEFERRED MANUAL\n";
        } else {
            sql += String.format("REFRESH DEFERRED MANUAL %s\n", refreshSchema);
        }
        if (mvProperties == null || mvProperties.isEmpty()) {
            sql += "PROPERTIES (  " +
                    "\"force_external_table_query_rewrite\"=\"true\"," +
                    "\"replication_num\"=\"1\"" +
                    ") ";
        }
        sql += String.format("AS \n %s;", definedQuery);
        return sql;
    }
}
